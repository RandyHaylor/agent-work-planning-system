# Module specs

Level 5. In progress. Work runs in rounds: questions, answers, research and initial design, next questions, repeat (see `process-levels.md`).

## Round 1 decisions (user, 2026-11-23)

1. **Existing data:** fresh schema; existing data isn't migrated.
2. **Node content (researched, approved).** Nodes stay an adjacency list (`parent_id`). The node row holds title, level label, context summary and its last-verified date. Everything else (requirements, notes, research, worker responses) is content items attached to the node, each with descriptive tags (not fixed roles), its own version history and permissions. Quote pointers link a content item to a quote and a range. Sources: [tree models compared](https://dev.to/dowerdev/implementing-hierarchical-data-structures-in-postgresql-ltree-vs-adjacency-list-vs-closure-table-2jpb), [Neon ltree docs](https://neon.tech/docs/extensions/ltree). The content-item split is the agent's reasoning, not from a source.
3. **The core (researched, approved).** Ports and adapters: a new core holding all operations, with no HTTP or database code; storage behind an interface with Postgres as the implementation; FastAPI and the CLI are thin layers over the same operations; Gradio calls HTTP. Written fresh against the new schema, reusing the existing pure parts where they fit (the `permissions.py` approach, admin sessions, backups, the isolated test runner). Sources: [ports and adapters in Python](https://dev.to/elpic/hexagonal-architecture-in-python-wiring-adapters-dependency-injection-and-the-application-layer-61l), [FastAPI and CLI over shared services](https://github.com/eefahd/python-clean-architecture).

## Module tree v5 (APPROVED by the user, 2026-11-23, in Slack: "approve v5")

Boundary level: every module, small and big, with nesting. Interfaces and types come next, module by module (level 5 phase 2).

```
main.py                                   knows nothing concrete: loads generic interfaces, passes each its config uninterpreted
configuration/                            reads injected config files; hands each module its own section

server/
  domain/                                 no I/O, no HTTP, no database
    access/                               who may do what
      principal                           who is acting: admin, planner, worker, quote client (no reviewer role; spec: 05-spec-access.md)
      permission_policy                   rules, incl. who may change a node's state (carried)
    authentication/                       credential -> principal
      password_hashing                    PBKDF2 (carried)
      token_hashing                       SHA-256 digests (carried)
      agent_session_keys                  persistent keys so agents can resume (carried pattern)
      admin_session                       temporary; human types a password only they know in a popup (carried pattern)
      credential_issuer                   mint, rotate, revoke; per-install quote key
      credential_storage_port
    project_tree/                         one generic node type
      node                                node, state, level label, context summary + last verified
      level_placement_rules               levels 1-4 linear, branching from 5; supplementary tasks exempt at any level
      node_editor                         create, update, move, abandon (never delete); summary updated on every change
      node_content                        content on a node; text stored as fixed references (superseded-by chain on edit)
      tree_storage_port
    context_assembly/
      context_assembler                   ancestors' context_summary + node's own content -> pre-prompt (spec: 05-spec-context-assembly.md)
    references/                           one reference system for user quotes AND documents
      reference_types                     Reference (one fixed item: origin, SHA-256, metadata, superseded-by), Citation (reference ID + line range)
      citing_and_rendering                pointer validation, server-rendered quoted text, follows superseded-by chain
      temp_cache_lifecycle                per-agent temp cache, a separate store (fetching agent + admin only); cite moves an item into references; TTL purge
      ingestion                           synced user exchanges in; anything the reader loads (URL, uploaded file, web search) -> document_extraction -> temp cache
      reference_storage_port
      temp_cache_storage_port
      source_fetcher_port                 any source the reader loads, not web-only
      (knowledge_base origin: the existing knowledge-base system carries over; assigned KBs readable per access)
    agent_registry/                       every agent session referenced, keyed by agent ID; optional host, platform, model,
                                          path, system, URL, first/last seen; never deleted
    review_dispatch/                      sends a review node to an available reviewer client, never to two
    task_assignment/                      planner/admin assigns a task node and mints the worker's scoped token
  commands/                               every action, reads and writes
    command_runner                        permission check -> transaction (read-only for reads) -> run
    request_authorizer
    <one class per command>               nested only by shared mechanics, never by subject
  storage/                                SQLAlchemy Core (no ORM)
    engine_setup                          engine + transactions (with engine.begin() is the unit of work)
    postgres_tree_store                   implements tree_storage_port
    postgres_reference_store              implements reference_storage_port
    postgres_temp_cache_store             implements temp_cache_storage_port (wiped freely)
    postgres_credential_store             implements credential_storage_port
    postgres_agent_registry_store         implements the agent registry's storage port
    migrations/                           Alembic
  adapters/
    http_source_fetcher                   one implementation of source_fetcher_port (URLs); catches HTTP errors and failure markers
    uploaded_file_source                  another: file bytes uploaded by the CLI / local client (Word, PDF, ...)
  http_api/                               protocol only
    application                           FastAPI wiring, TLS (carried)
    credential_dependency
    command_routes                        every route -> a command
    error_mapping
  database_backup/                        one module: encrypted pg_dump, retention, restore (carried)
  bootstrap/                              first-time setup: migrations, root nodes, admin password, backup keypair

document_extraction/                      own package; bytes + metadata -> citable text; no network, no DB
  text_decoding                           header charset -> meta tag -> charset_normalizer
  content_type_detection                  header + leading bytes
  fallback_runner                         generic: tries interchangeable strategies in order; reports which one was used
  text_normalization                      line endings, soft wrap, JSON pretty-print -> citable form
  strategies/                             one per extractor
    trafilatura_markdown
    readabilipy_markdownify
    whole_page_markdownify
    pypdf_text
    pdfminer_text
    docx_text
    text_passthrough
    json_pretty_print
    jsonl_passthrough

fastReader/                               our copy, kept mostly intact; adapted to the temp cache store + cite (spec: 05-spec-references-and-reader.md)
quick_json_reader/                        our copy (JavaScript, Node), kept mostly intact; results as line ranges of stored text
prompt_builder/                           our copy of ai-rule-builder (Python package, data, tests, website), kept mostly intact;
                                          the container for each role's rules / pre-prompt guidance; served per role;
                                          presets saved with the server's files; the planner launches its website for the user

api_client/                               one client for the HTTPS API, used by cli, web_ui, local_client
admin_login/                              the password popup that starts an admin session (cli, web_ui, agent)
cli/                                      very thin hand-written wrapper so agents can call the server (uses api_client)
  entry_point
web_ui/                                   Gradio; no logic; same API as an admin agent (true MVC)
  gradio_application
  pages/
    node_list_page                        filtered by state
    node_detail_page
    login_page
local_client/                             Python, beside the agent harness
  quote_capture/                          local client cache of every exchange (SoT raw log writer/reader) + reference_sync
                                          (only referenced exchanges go to the server; spec: 05-spec-quote-capture.md)
  review_worker/                          receives review jobs from the server, runs them via a harness adapter
  harness_adapters/
    ai_cli_adapter_interface              the harness interface (SoT)
    claude_code/                          adapter, UserPromptSubmit hook, transcript reader, AskUserQuestion capture,
                                          installer (SoT); headless sessions via claude -p
    (codex/ later: not in v1; plugs in through the same interface)
  client_credentials                      the install's quote key
```

Dropped since v4: tree_export, operations_tooling, user_quotes and document_sources (merged into references), node_claimer and claiming, node_state_views (now read commands), quality checks, a separate queries module, yoyo, schema.sql.

## Superseded: module tree v4 (kept for history; v5 above replaces it)

**Module** means a normal code module: a cohesive unit with a clear responsibility and an interface, often small (a single file, one strategy, or a folder). Modules nest: a parent module exposes one public interface and keeps its children private. Siblings use each other only through those public interfaces, never each other's children.

**Dependency direction** (one way only): interfaces → commands → domain → storage ports. Storage and harness adapters implement ports declared further in. Nothing in the domain knows about HTTP, Postgres or any harness.

**Patterns used** only where they add value: Strategy (fetchers, converters, scanners, harness adapters), Adapter (Postgres stores, harness adapters), Factory (picking a converter by content type, an adapter by configured harness), Command (one class per command), Facade (a package's public interface where it hides several parts; the shared API client).

"(carried)" = adapted from this repo; "(SoT)", "(fastReader)", "(quick-json-reader)" = adapted from that repo.

```
server/
  domain/                                  no I/O
    access/                                public: PermissionPolicy, Principal
      principal.py                         principal and role types
      permission_policy.py (carried)       who may do what, incl. who may change a node's state
    authentication/                        public: CredentialAuthenticator, CredentialIssuer
      password_hashing.py (carried)
      token_hashing.py (carried)
      admin_session_store.py (carried)
      credential_issuer.py                 mint, rotate, revoke with cascade; quote credentials
      credential_authenticator.py          credential -> Principal
      credential_storage_port.py
    project_tree/                          public: ProjectTree (facade), node types, TreeStoragePort
      node.py                              node, content, state, level label
      level_placement_rules.py             levels 1-4 linear; where a node may go
      node_editor.py                       create, update, move, delete; summary + verified date on every change
      node_content_editor.py               add and edit content, with version history
      node_state_views.py                  read-only views by state ("queues")
      tree_storage_port.py
    context_assembly/                      public: ContextAssembler
      context_assembler.py                 ancestor summaries + inherited requirements -> pre-prompt
    references/                            APPROVED (round 5) one reference system for user quotes AND documents
                                           shared core: immutable text versions (SHA-256), citation = version ID + line range,
                                           pointer validation, server-rendered text, supersession/version links (SoT-derived)
                                           origin per source: user capture, web fetch, later knowledge-base code
                                           origin policies: fetched = shared temp cache with TTL + promotion on first citation;
                                           user = approval, approval valid only for the exact text shown
                                           ingestion paths: quote capture (local client); fetch (port) -> document_extraction
                                           storage through a port
  adapters/http_source_fetcher.py          APPROVED (round 4) implements SourceFetcherPort; plain HTTP, keeps error bodies

document_extraction/                       APPROVED (round 4) own package; bytes + metadata -> citable text; no network, no DB
  public: ExtractionPipeline, ExtractionStrategy, QualityCheck, StrategyRegistry
  strategies/                              one class per extractor (from background research; incl. ported fastReader HTML)
  quality_checks/                          one class per check
  content_type_detection.py                header + leading bytes + meta charset
  text_normalization.py                    line endings, soft wrap, JSON pretty-print -> citable form

document_reader/                           APPROVED (round 4) own package; pure over citable text; public: DocumentReader (facade)
  structure/                               Marker, Manifest, LineIndex (fastReader)
    scanners/                              strategy per kind: heading, indent depth, bracket depth, tag depth (fastReader)
  navigation/                              table of contents, section -> line range, previews (fastReader)
  search/                                  hits with containing sections (fastReader)
  json_view/                               quick-json-reader Python port; reports line ranges of the stored text
  commands/                                public: CommandRunner
    command_runner.py                      authorize -> unit of work -> run command
    request_authorizer.py
    unit_of_work.py
    <command_name>.py                      one small class per command (ApproveWithNote, CreateSupplementaryTask, TurnInTask, AssignTask, ...)
  storage/                                 Postgres; implements the ports (Adapter)
    schema.sql                             fresh schema, version triggers
    database_connection.py (carried)
    postgres_tree_store.py
    postgres_quote_store.py
    postgres_source_store.py
    postgres_credential_store.py
  http_api/                                protocol only
    application.py (carried)               FastAPI wiring, TLS
    credential_dependency.py
    command_routes.py                      route -> command class
    error_mapping.py
  operations_tooling/ (carried)
    live_export.py
    encrypted_backup.py
    bootstrap.py

api_client/                                own package; Facade used by the CLI and web UI
  api_client.py

cli/                                       HTTPS client
  openapi_command_generator.py
  entry_point.py

web_ui/                                    Gradio, HTTPS client, no logic
  gradio_application.py
  pages/
    tree_view_page.py                      tree, addendums
    approval_page.py
    escalation_page.py

local_client/                              own package; public: LocalClient
  client_configuration.py
  session_project_link.py
  prompt_capture.py (SoT)
  transcript_context_reader.py (SoT)
  reviewer_loop.py                         receives review jobs sent by the server, runs them through an adapter
  harness_adapters/                        public: HarnessAdapter (strategy), AdapterFactory
    harness_adapter.py (SoT)               interface
    adapter_factory.py                     picks the adapter for the configured harness
    claude_code/
      hook_entry.py (SoT)
      headless_session.py (SoT)            claude -p
    codex/
      hook_entry.py
      headless_session.py                  codex exec
```

**Review is not a code area.** A review is an ordinary task: the server sends the review node to an available reviewer client, which, gets standard review instructions (configuration text adapted from SoT, including title checks), and turns in its verdict as its response. Submitting for review and recording a verdict are command classes.

Node state is a plain attribute on the node; who may change it to what is a rule in the permission policy.

## Existing-solutions research (round 3, 2026-11-23; recommendations, not approved)

Per the no-reinventing-wheels rule, each module that may have an off-the-shelf answer was researched before specs.

| Module | Finding | Recommendation |
|---|---|---|
| `converters/html_to_text.py` | Trafilatura and Readability are the strongest heuristic main-text extractors; trafilatura leaks less boilerplate, Readability keeps slightly more content; BeautifulSoup is a parser, not an extractor. Benchmarks are mostly self-reported or small vendor tests. ([trafilatura docs](https://trafilatura.readthedocs.io/en/latest/evaluation.html), [SIGIR 2025 paper](https://dias.users.greyc.fr/publications/sigir2025.pdf), [vendor comparison](https://thunderbit.com/blog/trafilatura)) | Use **trafilatura** behind the converter interface. Note: for citations we may want the whole page text, not only the main article; decide in the spec |
| `converters/pdf_to_text.py` | PyMuPDF is AGPL or commercial. pypdf is pure Python and permissively licensed (sources disagree on BSD vs MIT). pdfplumber suits tables. ([PyMuPDF about](https://pymupdf.readthedocs.io/en/latest/about.html), [pypdf comparisons](https://pypdf.readthedocs.io/en/stable/meta/comparisons.html), [2026 comparison](https://www.nutrient.io/blog/best-python-pdf-libraries/)) | Use **pypdf**; avoid PyMuPDF for licensing. Check pypdf's license file before adopting |
| `cli/openapi_command_generator.py` | Existing Python tools build a CLI from an OpenAPI spec: **specli** (Typer, auth, retries; runtime or generated) and **openapi-cli-gen** (runtime or pip package; flattens nested bodies into flags; reads auth from the spec). Maintenance status not verified. ([specli](https://pypi.org/project/specli/), [openapi-cli-gen](https://pypi.org/project/openapi-cli-gen/), [openapi2cli](https://pypi.org/project/openapi2cli/)) | **Don't write a generator.** Spike specli and openapi-cli-gen against our spec and pick one |
| `project_tree/node_claimer.py` | The conventional Postgres pattern: one `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING`, with a claimed-by and claimed-at stamp and a reset for stale claims. Separate SELECT then UPDATE races. ([Neon guide](https://neon.com/guides/queue-system), [Encore article](https://encore.dev/articles/postgres-job-queue-skip-locked), [PgQueuer reference](https://janbjorge.github.io/pgqueuer/reference/skip-locked/)) | Use that pattern; no queue library needed |
| `storage/` migrations | Alembic is built around SQLAlchemy, which we don't use. yoyo-migrations runs plain SQL or Python migrations without an ORM; small plain-SQL runners also exist. ([yoyo notes](https://lyz-code.github.io/blue-book/coding/python/yoyo), [Alembic reference](https://realpython.com/ref/tools/alembic/), [sqlstep comparison](https://pypi.org/project/sqlstep/)) | Use **yoyo-migrations** with plain SQL files; not Alembic |
| `authentication/password_hashing.py` | The repo today uses PBKDF2-HMAC-SHA256 from the standard library. OWASP's first choice is Argon2id (m=19456, t=2, p=1), e.g. via argon2-cffi. ([OWASP cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)) | **Keep the carried PBKDF2** (600,000 iterations, `admin.py:20`). Nothing is wrong with it; it was only listed because every candidate module was researched |
| `authentication/token_hashing.py` | The repo stores a SHA-256 digest of each token. The search found no source covering API tokens specifically; storing a digest of a high-entropy random token is common practice, but that is general knowledge, not verified here | Keep the carried approach; mark as unverified |
| `document_reader/` | Our own fastReader and quick-json-reader | Adapt them, as planned |

## Round 2 decisions (user, 2026-11-23)

1. **Agent acting as the user is admin.** The agent uses an admin session, obtained the same way (the user types the password in a login window), and can do everything admin can.
2. **Quote-submission credential:** the admin mints a dedicated credential per local client install. It can only submit user quotes and is revocable like any token.
3. **Document fetching:** plain HTTP plus converters for HTML and PDF to text, building on fastReader's `web.py`. JavaScript-only pages fail with a clear error.
4. **Isolation:** left to the user and primary agent. The system recommends worktrees or branches and records which branch a task's work is on.
5. **Running acceptance tests:** the planner runs them, or assigns tasks for workers to run them; the choice depends on project size. User: "planner can run them OR can assign tasks to have workers run them. Depending on project size the choice may differ"
4. **No separate MCP server.** The HTTPS interface is already agent-first; a permission level lets an agent act as the user. User: "our https interface is already LIKE a mcp server, so we don't need a separate mcp server - our tool is literally already an ai agent first tool! we simply need a permission level that allows an agent to act as a user - do all actions the user could do in the web interface and more. one more reason to have the web interface not contain business logic AT ALL - PLEASE FIGHT THE CANCER OF MODERN DEVS PUTTING LOGIC IN UI PLEASE PLEASE PLEASE"
5. **Gradio:** an HTTP client only, exactly like any other client.
6. **Local client language:** Python.
7. **Queues:** Postgres tables.
8. **Reviewers:** the server deploys reviews to a connected client instance configured to act as a reviewer. User: "it was clearly stated that the server deploys the reviews from a connected client instance configured to act as a reviewer"

## Round 4 decisions (user, 2026-11-23)

1. **fastReader and quick-json-reader are their own package in this repo, adapted for our needs, not bolted on as is.** User: "quick-json-reader and fastReader coming in DO need to be adapted and possibly not just wrenched on as is but converted for the purpose we have some specific needs for them. even though we're including them, they still do need to be treated as their own module/package in this repo, so we need to plan that well". Module tree v4 is therefore not approved yet.
2. **Broad website support, tested.** User: "we do want to ensure it works broadly and brings in features - we may need to extend it to ensure it supports a broad range of website, etc, so we'll want to do some testing as well. we can also do inital testing directly with fast reader/json reader directly as they currently are functional after all."
3. **Two cache tiers.** User: "lets say reserched sites are stored to a temp cache, but then referenced docs are moved to a permanent project repo to reference". Details chosen by the user:
   - **Promotion:** a document version enters a project's permanent store on its first citation. Nothing cited can expire.
   - **Temp cache scope:** shared server-wide; a URL fetched by any project is reused by others while fresh.
   - **Freshness:** a configurable TTL (server setting). Within it a URL is reused; after it, a request fetches a new version. Uncited versions older than the TTL are purged. A caller can force a refetch.
   - **Citable text (user chose normalizing at extraction):** extraction strategies write citable text. JSON is pretty-printed with a fixed indent and key order kept; JSONL stays one record per line; prose is soft-wrapped at a fixed width. Citations are line ranges only; raw bytes are kept for reference.
   - **Storage:** each version's raw bytes and extracted text are stored once as an immutable blob keyed by full SHA-256; a project's store is references plus per-project metadata. A blob is kept while any project or fresh temp entry references it.
4. **Web extraction is a strategy pattern with selection and automatic fallback.** User: "We need a clean strategy pattern for web extraction so we can port in and choose from a list of different options - even automatically trying mlutiple approaches after failtures." Concrete strategies and failure checks come from background research and testing; the design proceeds without waiting. User: "saying 'we need a generic strategy adapter/wrapper and way to choose/fall back to strategies' solves the design issue at a higher level letting us continue here"

5. **Retrieval catches its own failures.** No separate check step or second fetch. User: "the primary retrieve attempt can still catch errors and look for markers of failure. you have not convinced me a separate check fetch adds anythihg but complexity"

## Round 5: module walkthrough at boundary level (user, 2026-11-23)

Approved one at a time: `access`, `authentication`, `project_tree`, `context_assembly`.

- **User quotes and document sources are one reference system** (`server/domain/references/`). User: "We need to actually evaluate whether or not we can make this code overlap with the code for storing references from sources. I feel like we're building two very similar systems for referencing and hty're gion to be built very differently. I'd rather they share the same strcture/types/logic/etc". The user then approved merging them into `references`, with origin-specific rules as small policies and separate ingestion paths.

- Approved: `commands`, `storage`, `http_api`.
- **`operations_tooling` is split into three modules** (it grouped unrelated things): `tree_export` (renders a node subtree as readable files, plus an atomic file writer; from `backup.py`), `database_backup` (encrypted pg_dump, retention, restore; triggered when a task is done or on demand; from `full_backup.py`), `bootstrap` (first-time setup in one transaction: migrations, root nodes, admin password and backup keypair via authentication; from `bootstrap.py`). User: "split into three - I am noticing you having a MASSIVE pressure to group things to 1: avoid small modules or 2: group dissimilar things into modules because they share some common attribute, despite being mechanically different. It keeps coming up. We need to ensure you stop, and we need to ensure prompting goes in that is super clear in this system how to split up these modules."

- Approved: `api_client`, `cli` (commands generated by the library the spike picks; the admin login window's home is a recheck item).
- **`web_ui`: generic pages** (node list filtered by state, node detail, login), on the user's condition: "as long as it's truly no logic, and the interface the https gradio web client uses is also usable the same way by an admin agent (i.e. mcp), so no function of the website can depend on the actual website - true mvc".
- **`local_client` nested:** `quote_capture/`, `review_worker/`, `harness_adapters/` (per harness: a capture-hook strategy and a session-runner strategy), `client_credentials`; all use the same API client.
- **Recheck 2, references kept simple.** User worried nesting implied special types: "I"m worried this is implying these all get their own special types when it can be way more simple". Adopted: one set of data types for everything, `Source` (with an `origin` field, e.g. user, web), `TextVersion` (immutable), `Citation` (version + line range); no subtypes. Code split only where reasons to change differ: citing and rendering; temp cache lifecycle (TTL, promotion, purge); ingestion. Origin rules are plain checks on `origin`, not strategy classes.
- **Recheck 3, storage:** one `postgres_reference_store`, `migrations/` (plain SQL) replacing `schema.sql`, `postgres_unit_of_work`; each implements exactly one domain port.
- **Recheck 4, node content reuses references' immutable text versions** (one version mechanism for all text).
- **No claiming.** "Claiming" was the agent's wording, not the user's design. User: "I feel like this system is set up so a planner/admin assigns tasks." Task nodes are assigned by the planner or admin, who mints the worker's scoped token; workers never pull work. Reviews are sent by the server to an available reviewer client; never sending one review to two reviewers is an internal detail of review dispatch. `node_claimer` and the claim command are dropped; the level 3 queue row is corrected. The research row on SKIP LOCKED stays as background for review dispatch.
- **Recheck 6 and 7, reads are commands.** User: "isn't read also a command". One `commands` module and one `CommandRunner`; read commands (nodes by state, worker context, reading a cited source through `document_reader`, table of contents, search) only read, run in a read-only transaction with the same permission check. No separate queries module; `node_state_views` leaves `project_tree`.
- **Recheck 5, standard database interface: SQLAlchemy Core (no ORM).** User: "surely there are generic db interface abstractions!" and "i can't imagine we need to invent this wheel here - there must be generic interfaces that are industry standard". The user chose SQLAlchemy Core: engine, connections, transactions via `with engine.begin()` (this is the unit of work; no homemade one), plain SQL via `text()` allowed. Migrations: Alembic (replaces the yoyo recommendation, which assumed no SQLAlchemy). Sources: [SQLAlchemy Core connections](https://docs.sqlalchemy.org/en/20/core/connections.html), [PEP 249](https://peps.python.org/pep-0249/). Command classes nest only by shared mechanics, never by subject.
- **Recheck 8-13 (answered in Slack, questions1.md):**
  - **8, extraction:** decoding is its own module; the fallback loop is generic. User: "Pull decoding out. The fallback loop is logic and should be abstracted and generic: a strategy pattern, with extractors as interchangeable strategies."
  - **9, no quality checks.** User: "The reader interface tells the calling agent which extraction method was used, so it can ask for another. Obvious HTTP errors are caught and trigger the automatic fallback; if nothing works, return an error. No separate quality checks: the calling agent decides whether the text is readable." The quality-check part of the round 4 draft and research findings is dropped.
  - **10, tree_export dropped.** User asked to justify it ("Why save node trees to files at all? We're switching to Postgres to pull disparate systems into one unified, simple system."); it was carried over with no stated reason. User: "drop."
  - **11, database_backup stays one module.**
  - **12, composition root: main knows nothing concrete.** User: "main is completely abstracted and knows nothing about anything: not the UI stack, not the database type, nothing concrete. It calls generic interfaces and passes in their config without interpreting it, e.g. load user interface, passing a user-interface config.json. Concrete choices come only from injected config."
  - **13, authentication sessions kept as in the original app.** User: "Already decided in the original app: agent sessions have keys and persist so agents can resume. This is about keeping agents honest, not high security. Admin sessions are temporary: a popup asks the human for a password only they know, and then an agent can act as admin. Keep that pattern; I like patterns that keep agents out of something no matter what they do."
- **Module tree v5** (redrawn, posted in Slack as `module-tree-v5.md`): `configuration/` approved (user, Slack).
- **CLI is hand-written and thin; no OpenAPI generation, no spike.** The "generated from OpenAPI" wording was added by the agent in session 1 (commit b2b3eec) without a user quote. User: "Don't launch the spike. I don't want a generated CLI. The CLI should be a very thin hand-written wrapper so agents can call the server, which is what I thought we were doing." The round 3 research row on CLI generators is void.
## Phase 2: references (user, 2026-11-23, Slack questions2.md)

These override earlier wording where they conflict (the TextVersion type, "approval of user text", the shared temp cache, reuse within TTL).

1. **A user source is one captured exchange.** User: "A source is always a single item: one captured exchange, which is the user's message plus zero or an expandable amount of agent text before it. This was already specified and shouldn't have been asked. The full session transcript stays local in the harness client; when something is referenced, the client sends only that reference to the server to be stored. Everything uses the same singular format. Stop creating different types and formats for different situations when it isn't necessary."
2. **Web fetches.** User: "Cache each fetch with its URL, when it was pulled, and the other metadata. If content is identical (same hash), reuse what's there. No heavy reuse beyond that: a new web search does a new web search. This was already decided earlier."
3. **References are fixed; reading always goes live.** User: "References are fixed in time and are never updated or overwritten. Reading a page only puts it in the temp cache; once it's cited it becomes a permanent reference. The agent picks the extraction strategy through the interface and is told which one was used; if the result is bad, it tries another and moves on. Agents can see references and their metadata (URL, date pulled) and can read the cited lines within the larger stored text with line numbers; that's reading our store, not browsing. When an agent visits a URL, even one it found in a reference, the reader always goes to the live web and never to the local cache." This replaces round 4's "within the TTL a URL is reused" (agent flagged the conflict in Slack): always fetch live, dedupe identical content by hash; the TTL only purges uncited temp entries.
4. **No numbered versions; superseded-by chain.** User: "No numbered versions. References are fixed items. Citations to a superseded reference are never updated; when one is pulled, the system follows the superseded-by chain to the newest one. A superseded reference gets a 'superseded by <id>' note so the agent knows there was a change and can still view the deprecated one." Types are therefore `Reference` (one fixed item: origin, SHA-256, metadata, superseded-by) and `Citation` (reference ID + line range); `TextVersion` and `Source` are gone.
5. **User text is never approved.** User: "Wrong premise: user text is never approved. Captured user quotes are trusted because the hard code knows it's the user's text; that's the bedrock of this approach. The approval mechanism is only for unsupported harnesses (e.g. web agents) that can't store verbatim user quotes: the agent submits a proposal ('I suggest X, do you approve?'), the user approves or adds notes on the website, and that is recorded as a user response. The user approves agent proposals, never user text."
6. **Temp cache is per agent.** User: "Temp cache entries are visible only to the agent that fetched them and to the admin (for troubleshooting). Worker agents never see each other's cache. Once cited, an entry becomes a permanent reference visible to anyone who can see that node." Replaces "shared server-wide".
7. **Origins: `user`, `web`, `node`, `knowledge_base` now.** User: "The knowledge base already exists as a system."
   Confirmed by the user: "Always fetch live, deduplicate identical content by hash, and use the TTL only to purge uncited temp entries. To clarify: if an agent fetches a URL and the content is identical to what's already stored, reuse the stored copy. Never send an agent to locally cached content from a web search or URL visit. An agent that finds a reference on another node can cite that existing reference, but by its reference ID, not by its URL."
8. **One universal ReferenceLibrary.** User: "One universal ReferenceLibrary: you have an ID, you look it up. Keep it simple."

### Reader direction change (user, Slack, 2026-11-23)

- **The draft lost fastReader's functionality.** User: "I'm not comfortable with a web-specific fetch. I want a more universal interface into the reader, because it's not just web. It will read documents too (Word, PDF, whatever), and whatever it reads gets loaded into the cache so it can be cited and stored. fastReader was already built like that, with a lot of these problems solved ... I wanted fastReader implemented, adapted only enough to save the things it references. I'm worried we've stripped out a lot of important functionality." And: "the quick-json-reader plugin for fastReader should be integrated too, because it has useful functionality."
- **Vendor fastReader and quick-json-reader mostly intact.** User: "the project is getting big, so leave fastReader and the quick-json-reader plugin more or less intact and integrate them as modules. Vendor them: pull down a version into our codebase and edit our copy as needed, rather than depending on my GitHub-posted version. There's a lot in them already (the interactive help menu, a lot of testing), and they're robust, powerful tools. Don't plan to rewrite them now; implement and adapt them, changing only what's needed to work with the server's cache and references." This replaces the `document_reader` port in tree v5 and the earlier recommendation to port quick-json-reader to Python.
- **Draft 2 answers (references-and-reader-draft2.md):**
  - **Node is a requirement** (for quick-json-reader in JS). User: "Use Node for now as a requirement. It's not that big of a deal."
  - **Keep the DuckDuckGo scraper; reader is the only way to register a reference.** User: "Leave the DuckDuckGo scraper as is, and encourage agents to use it; I think it gives better results than other systems right now. Agents can use their own web search tools and find the sites they want to quote anywhere, but to register a reference they have to pull the URL up through the reader. Make that clear in prompting and tooling."
  - **Copied in as our own tools, not "vendored".** User: "I already said this: just pull a copy down and modify it directly. No updates from upstream are expected; I'm not updating or thinking about those apps. Don't call it vendoring, since that implied a bunch of stuff. We're copying them in as our own tools, to evolve as we want. Keep them as independent modules: no hard coding, no rigid coupling. Improve them as independent modules as the app needs." The word "vendor" above is superseded by this.
  - User: "I keep getting asked the same questions over and over. Before asking, check the recorded decisions and don't re-ask anything that's already been decided."
### Phase 2: project_tree (user, Slack questions3.md, 2026-11-23)

The user corrected premises in the agent's "already decided" list; fixed in `02-definition-of-done.md`, `03-high-level-plan.md`, `process-levels.md`.

1. **States: assigned, in progress, done, abandoned.** User: "Nodes are not reviewed; review is a task, not a node state. No in_review / review_failed / passed states. States: assigned, in progress (past assigned), done, abandoned (see 4)."
2. **No requirement inheritance.** User: "We don't pass requirements down to child nodes. What passes down is a generic context block; 'requirement' is a more specific thing."
3. **Escalations and tech spikes are sibling tasks placed before the raising task** (same mechanism, same code; see `process-levels.md`).
   - **Renamed: "requirement request", not "escalation".** User: "don't call them escalations; call them requirement requests, since that's closer to what's happening. A requirement request is a task. It can be raised by a worker (inserted before its task, same mechanism as a tech spike) and can be answered by the session and its parent, flowing up to the parent or even the user. It can also be placed preemptively as a normal task in a planned workflow, e.g. a research/tech spike task followed by a requirements-gathering task. That's a suggested approach, so a requirement request is just an ordinary task type." (Still one generic node type; "requirement request" is a label on an ordinary task.)
   - **Depends-on field; the orchestrator decides what runs.** User: "the planning/admin agent decides who runs, and it can choose to run things in parallel. Typically siblings run in order, but add a \"depends on\" field: a list of sibling nodes a task depends on. If it isn't specified, a task depends on the sibling before it by default. If it is specified, it can name one or more siblings. Example: siblings 1-4, where 3 and 4 both list only 1. Then once 1 is done, the orchestrating agent can see that 2, 3 and 4 could run in parallel, if that's allowed, possible or helpful." Confirmed by the user: "Order implies the dependency unless one is specified, but as a rule, when a task inserts a tech spike or requirement request as a sibling before itself, always add it to that task's depends-on."
   - **Agent session registry** (from review of project-tree-interface-draft1.md). User: "keep it as just an ID, but we need more data to identify an agent. Add a running registry (a table/list) of all the agent sessions we reference, keyed by that ID, with typical optional metadata fields such as host, platform, model, path, system and URL." Then: "make it its own small module, simple and quick. Don't overthink it; add it to the plan. Never delete entries: all of a project's session metadata is kept forever, even if the agent session is never used again or is deleted on disk. It won't fill the disk." Added as `server/domain/agent_registry/` (authentication only maps a credential to an agent ID).
   - Agent's notes (sent in Slack, not contradicted): no blocked/paused state is needed, since siblings run in order and an unfinished earlier sibling is the block; nodes need a sibling position; abandoned siblings are skipped. No reserved tags are needed; the passed-down context block is a field on the node row.
4. **No deletion: an 'abandoned' state.** User: "Give nodes an 'abandoned' status instead of deleting them."

### Phase 2: context_assembly (user, Slack, 2026-11-23)

1. **The node's own content plus a general summary of every node above.** User: "The node gets all of its own stuff. Then it gets a general summary for every node above it. The top node has a general summary of what the whole thing does, and each node has its own general 'this is what this accomplishes' that builds on the one above it, so stacking them all up paints a clear story. It doesn't include every requirement and detail of the tasks in the stack, because you're not asking it to do all that work, but you do want to give it the context."
2. **Abandoned ancestors are left out.** User: "Abandoned means gone."

### Phase 2: access (user, Slack questions4.md, 2026-11-23)

1. **No reviewer role.** User: "Keep it simple, nothing special. A reviewer is just an agent you ask questions; it's meant to be a simple call."
2. **One worker tool: create supplementary task.** User: "A literal tool the worker can call: create supplementary task. It creates a tech spike or requirement request type and provides the information on what it needs. The worker doesn't choose where it goes; it always goes right before its own task." (Replaces separate RaiseRequirementRequest / RaiseTechSpike commands with one `CreateSupplementaryTask`.)
3. **Whoever a requirement request is assigned to answers it.** User: "Whoever a requirement request is assigned to can answer it."
5. **What a worker can read (re-asked after the revert; user chose a):** its own task, its assembled context (ancestors' context summaries), references cited on nodes it can see, its own temp cache, and the knowledge bases assigned to it.
4. **REVERTED (user, 2026-11-23): the planner creates all tasks; tasks do not split themselves.** User: "I think I was focusing on the recursive dynamic solution and I started morphing this into that. still I like the changes and will keep them. revert to the planner creating all the tasksk though i was wrong about that we're not using recursion to have tasks split themselves up here. I do like a task being able to spawn a sibling tech spike, and I like the requirements request(or any escalation) being a task in the node tree as well that becomes an upstream sibling, removing the need for a separate queue." The other changes made tonight (no requirement inheritance, review as a task, sibling spikes/requirement requests, states, depends-on) stay. The note below is kept for history only and does NOT apply: "nodes with children aren't work nodes in the usual sense. Agents are never assigned a node that already has children. Tasks aren't born with children; a task's own session breaks it into child nodes, so a node with children implicitly already has a session. That session is what requirement requests flow up to. There's a review or test task at the end of the children that checks whether the work is done. Once all children are done, the parent task's session resumes to confirm the child tasks are completed, write a summary and mark the node done, or report an error up if it isn't done."

### Gap 1: process guidance (user, Slack questions6.md, 2026-11-23)

1. **Contents:** per-role guides + per-level process guidance (levels 1-7, question rounds, module commandments) + session-start rule injections (user chose 1a).
2. **Served by the server per role; only the planner learns the system.** User: "Spawned agents don't know about the system; the planner does. Only the planner needs system guidance. Workers don't learn the system (their task carries their context), but they should get a good bit of guidance on how to do work: my rules, how to do work right. Served per role."
3. **Authored with the user's AI prompt builder, copied in.** User: "Roll in the AI prompt generation tool I recently wrote. It already has a good system and a lot of really good rules, plus a website an agent can launch so the user can edit and tweak roles (called presets) and groupings of rules. Use its generic templates for roles, with groupings of rules assigned to each role." Brought in the same way as fastReader: copied in as our own module, adapted as needed. Source: `~/ai_skills_agents_resources/ai-rule-builder` (skill `ai-prompt-builder`; package `ai_prompt_builder`; latest commit 1c9a830).

5. **CORRECTED (user, terminal, 2026-11-23): pull in the whole tool, website included.** The agent misframed the study: the full prompt assembly is in Python (usable without the UI); the browser only has a duplicate. User: "can't the website allow updating the presets in a cool way? I'd say pull it in because it was really useful, not built wrong. The agent planner can load the web interface for the user so the user can see and edit the presets, right?" So ai-rule-builder is copied in as our own module like fastReader (Python package, data, tests AND its website), adapted only as needed (role -> preset mapping, guidance served per role). The planner launches the website for the user to view and edit presets. `guidance-draft1.md` (fresh re-implementation) is withdrawn. Item 4 below is superseded. Where edited presets are saved: alongside the server's files; user: "if it's pulled in then the prompts save along with the server's files somewhere maybe. doesn't really matter" (the tool's user-data folder is pointed at a folder the server reads; its `AI_PROMPT_BUILDER_HOME` setting already allows this).
4. **Superseded by 5. Revised (user, Slack): build our own small module from its logic, not a copy of the tool.** User: "Keep it very simple: 1. Double-check the claim that ai-rule-builder does prompt assembly in browser JS. I explicitly specified it had to be usable without the UI, so verify with evidence (file and line) before we act on it. 2. Scrape all the rules, plus the developer and technical presets/roles, from ai-rule-builder. 3. Take its logic, but build our own local module to serve us, using the same paradigm (role templates with groupings of rules). If logic really is in the UI, don't carry the UI over." Check result: the tool IS usable without the UI (Python `compose_prompt_text`, `ai_prompt_builder/ruleset.py:87-112`; CLI `compose` command, `command_line.py:196,340`), and the browser ALSO has its own copy of the assembly (`js/rule-selection-state.js:92-129`, used so the page works standalone). So the UI is not carried over. Rules and dev/technical presets are copied to `planning/source-material/ai-rule-builder/`.

### Audit answers (user, 2026-11-23)

Audit in `05-audit-2026-11-23.md`. User: "we added the prompt builder so it can help be the container for the rules/pre-propmt guidance for the different agent roles. i dont see what calls you nee from me on those". Already-decided items were aligned in the tree and specs without new decisions. Two open questions:
1. **Supplementary tasks are exempt from the levels 1-4 one-child rule** (user chose this): levels 1-4 keep one main child; tech spikes and requirement requests may sit beside it at any level.
2. **Planner token kept as today** (user chose this): a token scoped to one project, acting as that project's admin; admin stays the human-approved session.

### Gap 2: quote_capture (user, terminal, 2026-11-23)

User: "so source of truth solves this already for claude. that needs to be adapted for our client's adapter. lets take codex off the table but PLEASE build it with an interface so we can connect codex later." So: the local client's quote capture adapts source-of-truth's Claude Code capture into the Claude Code harness adapter; Codex is out of v1; the HarnessAdapter interface stays so Codex can be added later without changing anything else.
- **Design (user approved: "yes"):** copy source-of-truth's capture side into `local_client/` as our own code (from `~/ai_skills_agents_resources/source-of-truth`, commit d22d770), kept mostly intact: `ai_cli_adapter_interface.py` (the harness interface; Codex later = a second implementation), `ai_cli_adapter_claude_code.py`, the `UserPromptSubmit` hook (verbatim prompt + preceding agent output as pre-text, read from the transcript by `claude_cli_get_recent_agent_messages.py`; no Stop hook), `post_tool_use_capture_askuserquestion_answers.py` (answers to the planner's question dialogs), and `install.py` (hook scripts + settings.json patching). CORRECTED (user: "prompts are captured to a local client cache, only references are synced to server that was in spec"): `raw_input_log_writer.py` keeps writing every exchange to the local client cache; the only new piece sends an exchange to the server's `store_user_exchange` (quote key) when it is referenced.

### Phase 2: authentication (user, Slack, 2026-11-23)

1. **No global server access token; self-signed TLS for v1.** User: "Drop the global server access token; per-principal credentials over TLS are enough. For the first version, use a locally self-signed certificate and don't worry about it beyond that."

- **Temp cache is a separate store from references.** User: "drop the `permanent` flag. If it doesn't make things a lot more complicated, keep the temp cache as a separate store from the permanent references. Citing moves an item from the cache into the references store. That way clearing the cache is just wiping the cache store, with no risk of accidentally deleting references we want."
- Walkthrough complete. Next: the recheck items in `05-recheck-items.md`, one at a time; then a redrawn tree.

### Findings behind round 4 (2026-11-23)

- fastReader (about 2,200 lines, 108 tests pass): the scanners, TOC, search and section boundaries are pure logic and reuse cleanly. Its file cache (8-character hash keys, global `~/.fastReader`, `/tmp` outputs) and file-bound `commands/*` need replacing. Section indexes depend on scanner config, so citations must use line ranges.
- quick-json-reader (one 1,030-line JS file, Apache-2.0, 25 tests pass): a Python port is low effort. Its line numbers belong to its rendered view, not the stored text, so citations must point at the stored text.
- Baseline on 29 real pages: fastReader's current HTML-to-text returned nothing on 17 of 22 HTML pages (void `meta`/`link` tags in its skip list never close), never emits headings, decodes everything as UTF-8 and turns PDFs into garbage. trafilatura (markdown mode) handled most HTML well but truncated some pages (RFC 9110 to one section) and returns nothing for PDF, text and JSON. 4 sites blocked plain HTTP behind Cloudflare.
- Extractor research (21 strategies on the same 29 pages; NOT approved, to confirm at interface time). Suggested HTML order: trafilatura (markdown; already has its own readability/jusText fallback) → readabilipy + markdownify → whole-page markdownify (never failed; keeps nav). trafilatura lost content or headings on ~6 of 20 good pages (RFC 9110, lib.ru, PostgreSQL docs, GitHub README, cpython page, Aozora). PDF: pypdf (BSD-3, license file checked) → pdfminer.six; no PDF library gave real headings. Avoid html2text (GPL), pymupdf4llm (AGPL), marker (weights limit commercial use); drop newspaper4k, goose3, justext (plain text, no headings). Text passes through; JSON pretty-printed; JSONL validated. Decoding by header charset → meta tag → charset_normalizer gave no garbled text. Possible output checks: too short (<250 chars), under half the page's visible text, heading count far below the whole page's, garbled characters. Cloudflare challenges are documented by the `cf-mitigated: challenge` header ([Cloudflare docs](https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/)). Sources and data: [trafilatura evaluation](https://trafilatura.readthedocs.io/en/latest/evaluation.html), [trafilatura external.py](https://raw.githubusercontent.com/adbar/trafilatura/master/trafilatura/external.py), [pypdf LICENSE](https://raw.githubusercontent.com/py-pdf/pypdf/main/LICENSE), [PyMuPDF about](https://pymupdf.readthedocs.io/en/latest/about.html), [marker](https://github.com/datalab-to/marker).

