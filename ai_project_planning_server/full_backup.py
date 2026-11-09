"""Full encrypted database backup, retention, and restore.

A backup is a complete ``pg_dump`` of the planning database (custom format), encrypted so that
no password is needed to take one but the admin password is needed to read one:

- At bootstrap a RSA-4096 keypair is created. The public key is stored in ``meta`` in the clear.
  The private key is stored in ``meta`` encrypted with AES-256-GCM under a key derived from the
  admin password (PBKDF2-HMAC-SHA256, 600k iterations, fresh salt).
- Each backup: a random AES-256-GCM data key encrypts the dump; the data key is wrapped with the
  public key (RSA-OAEP, SHA-256). File layout: 4-byte magic ``APPB``, one JSON header line
  (version, timestamp, task_node_id, wrapped_key, nonce), then the ciphertext. The header line is
  the GCM associated data, so it cannot be altered without detection.
- Restore: the admin password unlocks the private key, the data key is unwrapped, the dump is
  decrypted and fed to ``pg_restore --clean --if-exists``.

Trigger: every time a task node under ``plans`` is set ``done`` (after the transaction commits),
and on demand with ``uv run ai-project-planning-server backup``.

Retention, applied after every backup: keep every backup of the last 10 task completions, the
oldest backup of each day, the oldest of each ISO week, the oldest of each month. Delete the rest.

``pg_dump``/``pg_restore``: used from PATH when present, otherwise run inside a throwaway
``postgres:16-alpine`` container (``PLANNER_POSTGRES_IMAGE``) reaching the database on the host.

Files live in ``PLANNER_FULL_BACKUP_DIR`` (default: ``full_backups/`` under the repo; when
``PLANNER_BACKUP_DIR`` is set and the first is not, ``<PLANNER_BACKUP_DIR>/full_backups`` so test
runs stay isolated). Name: ``<UTC timestamp>-task-<node id>.backup`` (``task-manual`` on demand).
"""
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ai_project_planning_server import db

MAGIC = b"APPB"
FORMAT_VERSION = 1
PBKDF2_ITERATIONS = 600_000
KEEP_LAST_TASKS = 10
META_PUBLIC_KEY = "backup_public_key"
META_PRIVATE_KEY = "backup_private_key_enc"
POSTGRES_IMAGE = os.environ.get("PLANNER_POSTGRES_IMAGE", "postgres:16-alpine")
TIMESTAMP_FMT = "%Y%m%dT%H%M%SZ"


class FullBackupError(Exception):
    pass


def backup_dir() -> Path:
    explicit = os.environ.get("PLANNER_FULL_BACKUP_DIR")
    if explicit:
        return Path(explicit)
    export_dir = os.environ.get("PLANNER_BACKUP_DIR")
    if export_dir:
        return Path(export_dir) / "full_backups"
    return db.REPO / "full_backups"


# ---------- keys ----------

def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_pem, public_pem)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private_pem, public_pem


def _password_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)


def encrypt_private_key(private_pem: bytes, password: str) -> str:
    """JSON string: salt, nonce, ciphertext (hex). AES-256-GCM under a PBKDF2 key from the password."""
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    ct = AESGCM(_password_key(password, salt)).encrypt(nonce, private_pem, b"private-key")
    return json.dumps({"salt": salt.hex(), "nonce": nonce.hex(), "ciphertext": ct.hex()})


def decrypt_private_key(blob: str, password: str) -> bytes:
    d = json.loads(blob)
    try:
        return AESGCM(_password_key(password, bytes.fromhex(d["salt"]))).decrypt(bytes.fromhex(d["nonce"]), bytes.fromhex(d["ciphertext"]), b"private-key")
    except Exception as e:
        raise FullBackupError("wrong admin password, or corrupted backup key") from e


def keys_present(conn) -> bool:
    return db.meta_get(conn, META_PUBLIC_KEY) is not None and db.meta_get(conn, META_PRIVATE_KEY) is not None


def ensure_keys(conn, password: str) -> bool:
    """Create and store the backup keypair if absent. Returns True if created."""
    if keys_present(conn):
        return False
    private_pem, public_pem = generate_keypair()
    for k, v in ((META_PUBLIC_KEY, public_pem.decode()), (META_PRIVATE_KEY, encrypt_private_key(private_pem, password))):
        conn.execute("INSERT INTO meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (k, v))
    return True


def on_password_change(conn, new_password: str, read_current_password: Callable[[], str]) -> str:
    """Keep the private key readable after the admin password changes: re-encrypt it with the new
    password, which needs the current one. Creates keys if none exist. Returns a message."""
    if not keys_present(conn):
        ensure_keys(conn, new_password)
        return "Backup keys created."
    private_pem = decrypt_private_key(db.meta_get(conn, META_PRIVATE_KEY), read_current_password())
    conn.execute("UPDATE meta SET value = %s WHERE key = %s", (encrypt_private_key(private_pem, new_password), META_PRIVATE_KEY))
    return "Backup key re-encrypted with the new password."


def load_private_key(conn, password: str):
    blob = db.meta_get(conn, META_PRIVATE_KEY)
    if blob is None:
        raise FullBackupError("no backup keys: run `uv run ai-project-planning-server init-backup-keys`")
    return serialization.load_pem_private_key(decrypt_private_key(blob, password), password=None)


# ---------- file format ----------

@dataclass(frozen=True)
class Header:
    version: int
    timestamp: str          # UTC, TIMESTAMP_FMT
    task_node_id: Optional[int]
    wrapped_key: str        # hex
    nonce: str              # hex

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "Header":
        d = json.loads(s)
        return cls(version=d["version"], timestamp=d["timestamp"], task_node_id=d.get("task_node_id"), wrapped_key=d["wrapped_key"], nonce=d["nonce"])


def encrypt_bytes(data: bytes, public_pem: bytes, task_node_id: Optional[int], timestamp: Optional[str] = None) -> bytes:
    public_key = serialization.load_pem_public_key(public_pem)
    data_key, nonce = AESGCM.generate_key(bit_length=256), secrets.token_bytes(12)
    wrapped = public_key.encrypt(data_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    header = Header(FORMAT_VERSION, timestamp or utc_now_stamp(), task_node_id, wrapped.hex(), nonce.hex())
    header_line = (header.to_json() + "\n").encode("utf-8")
    ct = AESGCM(data_key).encrypt(nonce, data, header_line)
    return MAGIC + header_line + ct


def read_header(blob: bytes) -> Header:
    if not blob.startswith(MAGIC):
        raise FullBackupError("not a planning server backup file")
    nl = blob.index(b"\n", len(MAGIC))
    return Header.from_json(blob[len(MAGIC):nl].decode("utf-8"))


def decrypt_bytes(blob: bytes, private_key) -> tuple[Header, bytes]:
    if not blob.startswith(MAGIC):
        raise FullBackupError("not a planning server backup file")
    nl = blob.index(b"\n", len(MAGIC))
    header_line, ct = blob[len(MAGIC):nl + 1], blob[nl + 1:]
    header = Header.from_json(header_line.decode("utf-8"))
    data_key = private_key.decrypt(bytes.fromhex(header.wrapped_key), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    try:
        return header, AESGCM(data_key).decrypt(bytes.fromhex(header.nonce), ct, header_line)
    except Exception as e:
        raise FullBackupError("backup file is corrupted or was tampered with") from e


# ---------- names and listing ----------

def utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FMT)


def file_name(timestamp: str, task_node_id: Optional[int]) -> str:
    return f"{timestamp}-task-{task_node_id if task_node_id is not None else 'manual'}.backup"


@dataclass(frozen=True)
class BackupFile:
    path: Path
    timestamp: datetime
    task_node_id: Optional[int]


def parse_name(path: Path) -> Optional[BackupFile]:
    name = path.name
    if not name.endswith(".backup") or "-task-" not in name:
        return None
    stamp, task = name[:-len(".backup")].split("-task-", 1)
    try:
        ts = datetime.strptime(stamp, TIMESTAMP_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return BackupFile(path, ts, None if task == "manual" else int(task))


def list_backups(directory: Optional[Path] = None) -> list[BackupFile]:
    directory = directory or backup_dir()
    if not directory.exists():
        return []
    out = [b for b in (parse_name(p) for p in directory.iterdir()) if b is not None]
    return sorted(out, key=lambda b: (b.timestamp, b.path.name))


# ---------- retention (pure) ----------

def select_to_keep(entries: Iterable[tuple[datetime, Optional[int]]], keep_last_tasks: int = KEEP_LAST_TASKS) -> set[int]:
    """Indexes into ``entries`` to keep. The oldest backup of each ISO week and of each month are
    pinned and sit outside the count. Of everything else, whatever triggered it, the ``keep_last_tasks``
    most recent are kept. The oldest backup of each day is also kept."""
    items = list(entries)
    keep: set[int] = set()
    order = sorted(range(len(items)), key=lambda i: items[i][0])
    pinned: set[int] = set()
    seen_day, seen_week, seen_month = set(), set(), set()
    for i in order:  # oldest first, so the first of each bucket is the oldest
        ts = items[i][0]
        day, week, month = ts.date(), ts.isocalendar()[:2], (ts.year, ts.month)
        if week not in seen_week:
            seen_week.add(week); pinned.add(i)
        if month not in seen_month:
            seen_month.add(month); pinned.add(i)
        if day not in seen_day:
            seen_day.add(day); keep.add(i)
    keep.update(pinned)
    counted = [i for i in order if i not in pinned]
    keep.update(counted[-keep_last_tasks:])
    return keep


def apply_retention(directory: Optional[Path] = None, just_written: Optional[Path] = None) -> list[Path]:
    """Delete backups outside the retention rules. Returns the deleted paths. ``just_written`` is
    accepted for call compatibility; the newest backup is always inside the last-ten rule."""
    files = list_backups(directory)
    keep = select_to_keep([(b.timestamp, b.task_node_id) for b in files])
    deleted = []
    for i, b in enumerate(files):
        if i not in keep:
            b.path.unlink()
            deleted.append(b.path)
    return deleted


# ---------- pg_dump / pg_restore ----------

def _docker_dsn_and_flags(dsn: str) -> tuple[str, list[str]]:
    """How a throwaway container reaches a database bound to the host's loopback."""
    if platform.system() == "Linux":
        return dsn, ["--network", "host"]
    for host in ("127.0.0.1", "localhost"):
        dsn = dsn.replace(f"@{host}:", "@host.docker.internal:")
    return dsn, ["--add-host", "host.docker.internal:host-gateway"]


def _pg_command(tool: str, args: list[str], dsn: str, mount: Optional[Path] = None) -> list[str]:
    if shutil.which(tool):
        return [tool] + args
    cdsn, flags = _docker_dsn_and_flags(dsn)
    cmd = ["docker", "run", "--rm", "-i"] + flags
    if mount is not None:
        cmd += ["-v", f"{mount}:/work"]
    return cmd + [POSTGRES_IMAGE, tool] + [a.replace(dsn, cdsn) for a in args]


def pg_dump(dsn: str) -> bytes:
    cmd = _pg_command("pg_dump", ["--format=custom", "--no-owner", "--no-privileges", f"--dbname={dsn}"], dsn)
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise FullBackupError(f"pg_dump failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def pg_restore_list(dump: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "dump"
        p.write_bytes(dump)
        local = shutil.which("pg_restore")
        cmd = _pg_command("pg_restore", ["--list", str(p) if local else "/work/dump"], "", mount=None if local else Path(tmp))
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise FullBackupError(f"pg_restore --list failed: {r.stderr.decode(errors='replace').strip()}")
        return r.stdout.decode(errors="replace")


def pg_restore(dsn: str, dump: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "dump"
        p.write_bytes(dump)
        local = shutil.which("pg_restore")
        args = ["--clean", "--if-exists", "--no-owner", "--no-privileges", f"--dbname={dsn}", str(p) if local else "/work/dump"]
        cmd = _pg_command("pg_restore", args, dsn, mount=None if local else Path(tmp))
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise FullBackupError(f"pg_restore failed: {r.stderr.decode(errors='replace').strip()}")


# ---------- operations ----------

def run_backup(conn, task_node_id: Optional[int], directory: Optional[Path] = None, dsn: Optional[str] = None) -> Path:
    """Dump, encrypt to the stored public key, write the file, apply retention. Synchronous: a
    task completion waits for the dump to finish."""
    public_pem = db.meta_get(conn, META_PUBLIC_KEY)
    if public_pem is None:
        raise FullBackupError("no backup keys: run `uv run ai-project-planning-server init-backup-keys`")
    directory = directory or backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_stamp()
    blob = encrypt_bytes(pg_dump(dsn or db.get_dsn()), public_pem.encode(), task_node_id, stamp)
    path = directory / file_name(stamp, task_node_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    apply_retention(directory, just_written=path)
    return path


def decrypt_backup_file(conn, path: Path, password: str) -> tuple[Header, bytes]:
    return decrypt_bytes(path.read_bytes(), load_private_key(conn, password))


def server_running(port: Optional[int] = None) -> bool:
    port = port or int(os.environ.get("PLANNER_PORT", "8787"))
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def restore(path: Path, password: str, confirm: Callable[[str], str] = input, force: bool = False, dsn: Optional[str] = None) -> Header:
    """Replace the database with the backup. Refuses while the server answers on its port unless
    ``force``; requires the word RESTORE from ``confirm`` unless ``force``."""
    if not force and server_running():
        raise FullBackupError("the server is running on its port; stop it before restoring")
    dsn = dsn or db.get_dsn()
    with db.connect() as conn:
        header, dump = decrypt_backup_file(conn, path, password)
    print(f"Backup {path.name}: taken {header.timestamp} UTC, task node {header.task_node_id if header.task_node_id is not None else 'manual'}.")
    print(f"This REPLACES every table in the database at {dsn.split('@')[-1]} with the backup's contents.")
    if not force and confirm("Type RESTORE to continue: ").strip() != "RESTORE":
        raise FullBackupError("restore cancelled")
    pg_restore(dsn, dump)
    return header


# ---------- CLI ----------

def cli_backup() -> int:
    with db.connect() as conn:
        path = run_backup(conn, None)
    print(f"Backup written: {path}")
    return 0


def cli_backups() -> int:
    files = list_backups()
    if not files:
        print(f"No backups in {backup_dir()}")
        return 0
    for b in files:
        print(f"{b.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC  task {b.task_node_id if b.task_node_id is not None else 'manual':>6}  {b.path}")
    return 0


def cli_restore(args: list[str]) -> int:
    import getpass
    if not args:
        raise SystemExit("usage: ai-project-planning-server restore <backup file> [--force]")
    path, force = Path(args[0]), "--force" in args
    if not path.exists():
        raise SystemExit(f"no such file: {path}")
    password = os.environ.get("PLANNER_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    try:
        restore(path, password, force=force)
    except FullBackupError as e:
        print(str(e), file=sys.stderr)
        return 1
    print("Restore complete. Start the server again.")
    return 0


def cli_init_keys() -> int:
    import getpass
    with db.connect() as conn:
        if not db.meta_get(conn, "admin_pw_hash"):
            raise SystemExit("not bootstrapped: run `uv run ai-project-planning-server bootstrap` first")
        if keys_present(conn):
            print("Backup keys already exist.")
            return 0
        from ai_project_planning_server import admin as A
        password = os.environ.get("PLANNER_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
        if not A.verify_password(password, db.meta_get(conn, "admin_pw_salt"), db.meta_get(conn, "admin_pw_hash")):
            raise SystemExit("wrong admin password")
        with conn.transaction():
            ensure_keys(conn, password)
    print("Backup keys created. Backups are encrypted to them from now on.")
    return 0
