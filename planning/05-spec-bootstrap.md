# Spec: bootstrap

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- Tree v5: `bootstrap/` "first-time setup: migrations, root nodes, admin password, backup keypair" (05-module-specs.md).
- Round 5: "`bootstrap` (first-time setup in one transaction: migrations, root nodes, admin password and backup keypair via authentication; from `bootstrap.py`)".
- "Admin sessions are temporary: a popup asks the human for a password only they know" (Recheck 13); PBKDF2 carried (05-spec-authentication.md).
- "Drop the global server access token" (Phase 2: authentication, 1): the old bootstrap's access-token step is not carried.
- Out of this build: "database_backup" (BUILD-DECISIONS-LOG #7).
- Definition of done: "`planning-server bootstrap`" (BUILD-PLAN.md); "Same Postgres container, new database `planning_system`" (log #2).

## Modules (nested)

```
server/bootstrap/                   public: Bootstrapper
  password_prompt                   carried read_password: env override (PLANNING_ADMIN_PASSWORD, warns), else getpass twice,
                                    policy check, the carried "SAVE THIS PASSWORD" warning
  database_creation                 creates database `planning_system` in the existing container if missing (CREATE DATABASE
                                    outside a transaction, via the server's maintenance DSN)
  first_time_setup                  one transaction: set admin password (AdminSessions / authentication), [root nodes: open item]
```

## Types

```python
@dataclass(frozen=True)
class BootstrapResult:
    already_bootstrapped: bool
    messages: tuple[str, ...]        # what was done, printed by the command
```

## Public interface

```python
class Bootstrapper:
    def __init__(self, section: ConfigSection, storage: Storage, authentication: AuthenticationSetup, prompt: PasswordPrompt)
    def bootstrap(self) -> BootstrapResult
        # ensure_database -> run_migrations -> if admin password already set: say so and stop
        # -> ask password -> one read_write transaction: store admin password hash
    def set_admin_password(self) -> BootstrapResult     # carried command; requires prior bootstrap
```

Steps in order, each one call: ensure database, migrate (Alembic `upgrade head`, outside the setup transaction since Alembic manages its own), check done, ask password, set up in one transaction. A second run is a no-op that says so. No token is printed; admin comes from `POST /admin/sessions`.

## Open items (not decided here)

- **Root nodes:** v5 says bootstrap creates "root nodes" (old server: root, kb, plans). The approved project_tree spec lets a project be a node with `parent_id None` (`POST /projects`). Whether any root nodes exist in the new tree is not recorded.
- **Backup keypair:** recorded as a bootstrap step, but database_backup is out of this build (log #7). This spec leaves the keypair step out until database_backup is built; carried `set_admin_password` therefore has no key re-encryption step yet.

## External integration tests (mocked Storage, AuthenticationSetup and PasswordPrompt; one real-Postgres test)

1. First run: database ensured, migrations run, password asked once, hash stored inside one transaction.
2. Second run: no password asked; result says already bootstrapped; nothing written.
3. A failure while storing leaves nothing stored (transaction rolled back).
4. `PLANNING_ADMIN_PASSWORD` skips the prompt and prints a warning; a password failing policy is rejected.
5. `set_admin_password` before bootstrap fails with a clear message; after, it replaces the hash and old password stops starting sessions.
6. Real Postgres: on a fresh `planning_system` database, bootstrap then `POST /admin/sessions` with the password returns a token.
