# Spec: database_backup

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

**Not in the first build** (BUILD-DECISIONS-LOG #7). Specced now so the scaffold can include it hollow.

One module: an encrypted `pg_dump` of the database, retention, and restore. Carried from the old server's `ai_project_planning_server/full_backup.py`, which already does all of this; the code is moved, not redesigned.

## Recorded decisions this builds on

- `database_backup` is its own module: "encrypted pg_dump, retention, restore; triggered when a task is done or on demand; from `full_backup.py`". User, on splitting `operations_tooling`: "split into three - I am noticing you having a MASSIVE pressure to group things ... because they share some common attribute, despite being mechanically different." (`05-module-specs.md`, Round 5)
- "**11, database_backup stays one module.**" (`05-module-specs.md`, Recheck 8-13)
- The core reuses existing pure parts, including "backups" (Round 1 decision 3).
- `bootstrap/`: "first-time setup: migrations, root nodes, admin password, backup keypair" (tree v5); "admin password and backup keypair via authentication" (Round 5).
- Same Postgres container, new database `planning_system` (BUILD-DECISIONS-LOG #2); tables on the shared `METADATA` (#5); main knows nothing concrete, each module gets its config section uninterpreted (Recheck 12).

## What is carried as-is from `full_backup.py`

- Keys: RSA-4096 keypair; public key stored in the clear; private key encrypted with AES-256-GCM under a PBKDF2-HMAC-SHA256 (600,000 iterations, fresh salt) key from the admin password. Re-encrypted when the admin password changes.
- File format: magic `APPB`, one JSON header line (version, timestamp, task_node_id, wrapped_key, nonce) used as GCM associated data, then the ciphertext. Data key per backup, wrapped with RSA-OAEP SHA-256.
- Name: `<UTC timestamp>-task-<node id>.backup` (`task-manual` on demand); written via temp file + rename; mode 0600.
- Retention after every backup: the oldest of each ISO week and each month pinned; the oldest of each day kept; of the rest, the 10 most recent kept (`select_to_keep`).
- `pg_dump --format=custom --no-owner --no-privileges`; restore with `pg_restore --clean --if-exists`. Tools from PATH, else a throwaway `postgres:16-alpine` container.
- Restore refuses while the server answers on its port and asks for the word RESTORE, unless forced.

## What changes

- Keys move from the old `meta` table to a `backup_keys` table declared on `METADATA` (one row).
- Settings come from the module's config section, not `PLANNER_*` environment variables.
- The `db` module calls become an injected SQLAlchemy `Connection` and a DSN from config.

## Nested modules

```
server/database_backup/
  backup_keys          keypair creation, private-key encryption under the admin password, re-encryption
  backup_file_format   encrypt / decrypt / read header (pure)
  retention_policy     select_to_keep (pure)
  postgres_dump_tool   pg_dump / pg_restore, local or in a container (the only subprocess code)
  backup_key_store     the backup_keys table (SQLAlchemy Core)
  database_backup      facade: take_backup, list_backups, restore, create_keys, rekey
```

## Types

```python
@dataclass(frozen=True)
class BackupHeader:
    version: int
    timestamp: str                  # UTC, %Y%m%dT%H%M%SZ
    task_node_id: NodeId | None     # None = on demand
    wrapped_key: str
    nonce: str

@dataclass(frozen=True)
class BackupFile:
    path: Path
    timestamp: datetime
    task_node_id: NodeId | None

class BackupError(Exception): ...   # dump/restore failure, missing keys, cancelled restore, server running
```

## Public interface

```python
class DatabaseBackup:
    def __init__(self, config: BackupConfig, key_store: BackupKeyStore, dump_tool: PostgresDumpTool)
    def create_keys(self, connection, admin_password: str) -> bool            # bootstrap; False if keys exist
    def rekey(self, connection, old_password: str, new_password: str) -> None # on admin password change
    def take_backup(self, connection, task_node_id: NodeId | None) -> Path    # dump, encrypt, write, retention
    def list_backups(self) -> list[BackupFile]
    def restore(self, path: Path, admin_password: str,
                confirm: Callable[[str], str], force: bool = False) -> BackupHeader

@dataclass(frozen=True)
class BackupConfig:
    directory: Path                 # where backup files go
    dsn: str
    container_image: str = "postgres:16-alpine"
    keep_last: int = 10
    server_port: int                # checked before restore
```

### Triggers

- **Task done:** the command that sets a node's state to `done` calls `take_backup(connection, node_id)` after its transaction commits. Synchronous, as before.
- **On demand:** `planning-server backup` (server-side CLI, beside `bootstrap` and `run`); `planning-server backups` lists; `planning-server restore <file>` prompts for the admin password and RESTORE. Restore is offline (server stopped), so it is a server-side command, not an HTTPS route.

## External integration tests (mock up front)

Mocks: `PostgresDumpTool` (returns fixed bytes; records restore input), a temp directory, an in-memory key store.

1. `create_keys` then `take_backup` writes one `.backup` file whose header names the task node; decrypting with the admin password returns the mocked dump bytes.
2. A wrong password cannot decrypt; a tampered header fails GCM authentication.
3. `rekey` keeps old backups readable with the new password and not the old one.
4. `take_backup` without keys raises `BackupError`.
5. Retention: a generated history over several weeks keeps exactly the carried rule's set (port `full_backup`'s existing tests).
6. `restore` refuses while the port answers, refuses without RESTORE, and passes the decrypted dump to the dump tool when confirmed.
7. Setting a task node `done` takes one backup after commit; a failed transaction takes none.
8. Real tools (marked, needs Docker/Postgres): dump and restore round-trip a small `planning_system` database.
