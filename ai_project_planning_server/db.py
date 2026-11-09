import os
import hashlib
import secrets
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"
SCHEMA = Path(__file__).with_name("schema.sql")
ACCESS_HEADER = "X-Server-Access"


ACCESS_KEY = "PLANNER_SERVER_ACCESS_TOKEN"


def read_access_token() -> str:
    """The server access token: PLANNER_SERVER_ACCESS_TOKEN from the environment, else from the
    repo's .env (written by init-env). Every request must carry it in the X-Server-Access header, so
    only something with local disk access can talk to the server at all."""
    token = os.environ.get(ACCESS_KEY) or read_env_file().get(ACCESS_KEY)
    if not token:
        raise SystemExit(f"no {ACCESS_KEY}: run `uv run ai-project-planning-server init-env` (writes .env), or set {ACCESS_KEY}")
    return token.strip()


def new_access_token() -> str:
    return "acc_" + secrets.token_urlsafe(32)


def ensure_access_token(path: Path = ENV_FILE) -> str:
    """The access token in use: the environment override, else .env's; a .env from before the token
    existed gets one appended. Returns the token."""
    if os.environ.get(ACCESS_KEY):
        return os.environ[ACCESS_KEY].strip()
    values = read_env_file(path)
    if values.get(ACCESS_KEY):
        return values[ACCESS_KEY]
    if not path.exists():
        raise SystemExit(f"{path} missing: run `uv run ai-project-planning-server init-env` first")
    token = new_access_token()
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{ACCESS_KEY}={token}\n")
    _owner_only(path)
    return token


def _owner_only(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def read_env_file(path: Path = ENV_FILE) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def get_dsn() -> str:
    """PLANNER_DSN from the environment, else from the repo's .env (written by init-env)."""
    dsn = os.environ.get("PLANNER_DSN") or read_env_file().get("PLANNER_DSN")
    if not dsn:
        raise SystemExit("no PLANNER_DSN: run `uv run ai-project-planning-server init-env` first (writes .env), or set PLANNER_DSN")
    return dsn


def write_env_file(db_port: str, path: Path = ENV_FILE) -> dict:
    """Write .env: the one local file holding what anything with disk access needs to reach the
    server (database password and DSN, server access token). Owner-only permissions. Refuses to
    overwrite an existing file."""
    if path.exists():
        raise SystemExit(f"{path} already exists; delete it to generate new secrets (the DB volume must be reset too)")
    password = secrets.token_urlsafe(24)
    values = {
        "PLANNER_DB_PASSWORD": password,
        "PLANNER_DB_PORT": db_port,
        "PLANNER_DSN": f"postgresql://planner:{password}@127.0.0.1:{db_port}/planner",
        ACCESS_KEY: new_access_token(),
    }
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    _owner_only(path)
    return values


def connect():
    return psycopg.connect(get_dsn(), row_factory=dict_row, autocommit=True)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> str:
    return "pln_" + secrets.token_urlsafe(32)


def apply_schema(conn):
    conn.execute(SCHEMA.read_text())


def ancestors_fn(conn):
    """Return a function node_id -> [node_id, parent, ..., root]. Empty if unknown."""
    def anc(node_id: int) -> list[int]:
        rows = conn.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT id, parent_id, 0 AS depth FROM nodes WHERE id = %s
                UNION ALL
                SELECT n.id, n.parent_id, c.depth + 1 FROM nodes n JOIN chain c ON n.id = c.parent_id
            )
            SELECT id FROM chain ORDER BY depth
            """,
            (node_id,),
        ).fetchall()
        return [r["id"] for r in rows]
    return anc


def meta_get(conn, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None
