# Spec: commands

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- Tree v5: `commands/` "every action, reads and writes"; `command_runner` "permission check -> transaction (read-only for reads) -> run"; `request_authorizer`; "<one class per command> nested only by shared mechanics, never by subject" (05-module-specs.md, "Module tree v5").
- "isn't read also a command" -> "One `commands` module and one `CommandRunner`; read commands ... only read, run in a read-only transaction with the same permission check." (Recheck 6 and 7).
- "`with engine.begin()` (this is the unit of work; no homemade one)" (Recheck 5).
- Worker tool: "A literal tool the worker can call: create supplementary task ... it always goes right before its own task." (Phase 2: access, 2).
- "planner/admin assigns a task node and mints the worker's scoped token" (tree v5, task_assignment); "task_assignment beyond assign+mint" out of this build (BUILD-DECISIONS-LOG #7).
- Errors: raise `NotFound`, `Forbidden`, `Invalid` from `planning_system.contract` (BUILD-PLAN.md, shared contract).

## Modules (nested)

```
server/commands/                     public: CommandRunner, Command, ReadCommand, WriteCommand, every command class
  command                            Command base types; Access = READ | WRITE
  command_runner                     authorize -> transaction (read-only for READ) -> run
  request_authorizer                 resolves the facts a permission needs (node, ancestors, citing nodes, temp entry)
                                     through the domain, asks access/PermissionPolicy, raises Forbidden
  services                           Services: domain facades built over the Stores of one transaction
  <command>.py                       one class per command, flat (list below)
  reader_view/                       nested by shared mechanic: resolve an id (temp cache id OR reference id) to
                                     readable text with its permission check, then run one fastReader / quick-json-reader view
    readable_text_resolver
    <reader view command>.py
```

## Types

```python
class Access(Enum): READ; WRITE

class Command(Protocol):
    access: Access
    def required_permission(self) -> Permission           # e.g. CanReadNode(node_id); data only
    def run(self, services: Services, principal: Principal) -> Result   # domain calls only, no HTTP, no SQL

@dataclass(frozen=True)
class Services:              # built per transaction by ServicesFactory(stores)
    tree: ProjectTree; references: ReferenceLibrary; temp_cache: TempCache; reader: Reader
    context: ContextAssembler; agents: AgentRegistry; issuer: CredentialIssuer
    admin_sessions: AdminSessions; guidance: RoleGuidance; policy: PermissionPolicy

class CommandRunner:
    def __init__(self, transactions: Transactions, services_factory: ServicesFactory, authorizer: RequestAuthorizer)
    def run(self, command: Command, principal: Principal | None) -> Result
        # 1 open read_only or read_write by command.access
        # 2 services = services_factory(stores_for(conn))
        # 3 authorizer.check(principal, command.required_permission(), services)  -> Forbidden
        # 4 return command.run(services, principal)

class RequestAuthorizer:
    def check(self, principal, permission: Permission, services) -> None
```

Permission check runs inside the transaction, because it needs tree facts read through the same connection; nothing is written before it passes.

## Command list (every route in BUILD-PLAN.md)

| Route | Command | Access |
|---|---|---|
| POST /admin/sessions | StartAdminSession (no principal; password checked by AdminSessions) | WRITE |
| GET /me | GetCurrentPrincipal | READ |
| POST /credentials | MintCredential | WRITE |
| POST /credentials/quote-key | MintQuoteKey | WRITE |
| POST /credentials/{id}/revoke | RevokeCredential | WRITE |
| POST /agents | RegisterAgent | WRITE |
| POST /projects | CreateProject | WRITE |
| POST /nodes | CreateNode | WRITE |
| GET /nodes/{id} | GetNode | READ |
| GET /nodes/{id}/children | ListChildren | READ |
| GET /nodes/{id}/ancestors | ListAncestors | READ |
| GET /nodes/{id}/ready-children | ListReadyChildren | READ |
| PATCH /nodes/{id} | UpdateNode | WRITE |
| POST /nodes/{id}/move | MoveNode | WRITE |
| POST /nodes/{id}/state | SetNodeState | WRITE |
| POST /nodes/{id}/assign | AssignTask (ProjectTree.assign + CredentialIssuer.mint worker token) | WRITE |
| POST /nodes/{id}/supplementary | CreateSupplementaryTask | WRITE |
| POST /nodes/{id}/content | AddNodeContent | WRITE |
| PUT /nodes/{id}/content/{reference_id} | ReplaceNodeContent | WRITE |
| GET /nodes/{id}/context | AssembleNodeContext | READ |
| POST /reader/load | LoadIntoReader (fetch/upload/search -> document_extraction -> temp cache) | WRITE |
| GET /reader/{id}/toc | reader_view/ReaderToc | READ |
| GET /reader/{id}/get | reader_view/ReaderGet | READ |
| POST /reader/search | reader_view/ReaderSearch | READ |
| POST /reader/{id}/json | reader_view/ReaderJson | READ |
| GET /reader/{id}/lines | reader_view/ReaderLines | READ |
| POST /reader/cite | CiteCacheItem (temp cache -> references, keeps id) | WRITE |
| GET /references/{id} | GetReference | READ |
| GET /references/{id}/lines | ReadReferenceLines | READ |
| POST /references/render | RenderCitation | READ |
| POST /references/user-exchange | StoreUserExchange (quote key only) | WRITE |
| GET /guidance/{role} | GetRoleGuidance | READ |
| GET /guidance/templates | ListGuidanceTemplates | READ |
| GET /guidance/rules | ListGuidanceRules | READ |

Facade methods with no route in BUILD-PLAN.md get no command now: CredentialIssuer.rotate, AdminSessions.end, AgentRegistry.get/list, temp cache purge (see open items).

## External integration tests (mocked Transactions, ServicesFactory and domain facades)

1. A READ command runs in `read_only`, a WRITE command in `read_write` (spy on Transactions).
2. A Forbidden from the authorizer stops the command before `run` and nothing is committed.
3. An error raised by `run` rolls back (the transaction context sees the exception).
4. Every route in the table has exactly one command class, and every command class appears in the table (test reads both lists).
5. AssignTask calls ProjectTree.assign and CredentialIssuer.mint(role="worker", scope_node_id=node) in the same transaction and returns both.
6. CreateSupplementaryTask by a worker on its own task calls ProjectTree.insert_before; on another task it is Forbidden.
7. reader_view commands resolve a temp cache id for its owner/admin and a reference id for anyone who can read a citing node; anything else Forbidden.
8. StartAdminSession runs with principal None; every other command with principal None is Forbidden.
9. StoreUserExchange with a non-quote principal is Forbidden; MintQuoteKey by non-admin is Forbidden.
