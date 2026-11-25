# Spec: storage

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- "The user chose SQLAlchemy Core: engine, connections, transactions via `with engine.begin()` (this is the unit of work; no homemade one), plain SQL via `text()` allowed. Migrations: Alembic" (05-module-specs.md, Recheck 5).
- "each implements exactly one domain port" (05-module-specs.md, Recheck 3).
- Ports and adapters: "storage behind an interface with Postgres as the implementation" (Round 1, decision 3).
- "keep the temp cache as a separate store from the permanent references. Citing moves an item from the cache into the references store. That way clearing the cache is just wiping the cache store" (Phase 2: authentication, temp cache note).
- "Cache each fetch with its URL, when it was pulled, and the other metadata. If content is identical (same hash), reuse what's there." (Phase 2: references, 2).
- Agent registry: "Never delete entries" (05-spec-agent-registry.md).
- "Each module declares its tables on one shared SQLAlchemy `MetaData`; one Alembic history generated after integration" (BUILD-DECISIONS-LOG #5); "Same Postgres container, new database `planning_system`" (#2).
- Fresh schema; existing data isn't migrated (Round 1, decision 1).

## Modules (nested)

```
server/storage/                       public: create_storage(section) -> Storage; the five store classes
  metadata                            METADATA (exists)
  engine_setup                        Engine from the config section; Transactions (read-write / read-only)
  postgres_tree_store                 implements TreeStoragePort; declares nodes, node_dependencies, node_content tables
  postgres_reference_store            implements ReferenceStoragePort; declares references table
  postgres_temp_cache_store           implements TempCacheStoragePort; declares temp_cache_entries table
  postgres_credential_store           implements CredentialStoragePort; declares credentials, admin_sessions, admin_password tables
  postgres_agent_registry_store       implements AgentRegistryStoragePort; declares agent_sessions table
  migrations/                         Alembic env.py (target_metadata = METADATA) + versions/; one initial revision
```

Each store owns its own tables (declared in its file on METADATA). Stores never call each other; a cross-store step (cite: temp -> references) is done by the domain inside one transaction.

## Types

```python
class Transactions:
    def read_write(self) -> ContextManager[Connection]   # with engine.begin(); commit on success, rollback on error
    def read_only(self) -> ContextManager[Connection]    # engine.begin() + SET TRANSACTION READ ONLY

@dataclass(frozen=True)
class Storage:                                           # what the server composition gets
    transactions: Transactions
    def stores_for(self, conn: Connection) -> Stores     # all five stores bound to that one connection

@dataclass(frozen=True)
class Stores:
    tree: TreeStoragePort
    references: ReferenceStoragePort
    temp_cache: TempCacheStoragePort
    credentials: CredentialStoragePort
    agent_registry: AgentRegistryStoragePort
```

Each store's constructor takes one `Connection`; it never opens or commits a transaction.

## Ports implemented (declared in the domain modules; methods here are the storage needs implied by the approved facades)

```python
TreeStoragePort:        get, children (position order), ancestors (recursive CTE, root first), insert, update,
                        set_positions, content_of, add_content, replace_content_ref
ReferenceStoragePort:   get, find_by_sha256, insert, set_superseded_by          # no update of text, no delete
TempCacheStoragePort:   get, insert, find_by_owner_and_sha256, list_for_owner, take (remove + return; used by cite),
                        purge_older_than(cutoff) -> int, wipe() -> int
CredentialStoragePort:  insert, find_by_digest, revoke (cascade to minted_by descendants), replace_digest,
                        get_admin_password_hash, set_admin_password_hash,
                        insert_admin_session, find_admin_session, end_admin_session
AgentRegistryStoragePort: upsert (keeps first_seen), get, list                   # no delete
```

Final method names follow the domain specs' port files at scaffold; storage adapts to them, never the reverse.

## Public interface

```python
def create_storage(section: ConfigSection) -> Storage   # section keys: dsn, pool options; uninterpreted by anyone else
def run_migrations(section: ConfigSection) -> None       # alembic upgrade head, used by bootstrap
```

## External integration tests (real Postgres: the `planning_system` database in the existing container, a throwaway schema per test run)

1. `read_write` commits on success and rolls back when the block raises.
2. `read_only` rejects an INSERT.
3. Each store round-trips its port's types (one test per method).
4. Tree: ancestors root first; children in position order; no delete method exists.
5. References: inserting text with an existing SHA-256 is found by `find_by_sha256`; text can't be updated.
6. Temp cache: `take` removes the entry; `purge_older_than` removes only older entries; `wipe` touches no other table.
7. Credentials: only digests stored; revoking a planner credential revokes the worker credentials it minted.
8. Agent registry: upsert keeps first_seen and updates last_seen.
9. `alembic upgrade head` on an empty database creates exactly the tables on METADATA (autogenerate diff empty).

Domain tests use in-memory fakes of the five ports (written at scaffold, beside each port).
