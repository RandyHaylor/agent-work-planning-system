# Module specs

Level 5. In progress. Work runs in rounds: questions, answers, research and initial design, next questions, repeat (see `process-levels.md`).

## Round 1 decisions (user, 2026-11-23)

1. **Existing data:** fresh schema; existing data isn't migrated.
2. **Node content (researched, approved).** Nodes stay an adjacency list (`parent_id`). The node row holds title, level label, context summary and its last-verified date. Everything else (requirements, notes, research, worker responses) is content items attached to the node, each with descriptive tags (not fixed roles), its own version history and permissions. Quote pointers link a content item to a quote and a range. Sources: [tree models compared](https://dev.to/dowerdev/implementing-hierarchical-data-structures-in-postgresql-ltree-vs-adjacency-list-vs-closure-table-2jpb), [Neon ltree docs](https://neon.tech/docs/extensions/ltree). The content-item split is the agent's reasoning, not from a source.
3. **The core (researched, approved).** Ports and adapters: a new core holding all operations, with no HTTP or database code; storage behind an interface with Postgres as the implementation; FastAPI and the CLI are thin layers over the same operations; Gradio calls HTTP. Written fresh against the new schema, reusing the existing pure parts where they fit (the `permissions.py` approach, admin sessions, backups, the isolated test runner). Sources: [ports and adapters in Python](https://dev.to/elpic/hexagonal-architecture-in-python-wiring-adapters-dependency-injection-and-the-application-layer-61l), [FastAPI and CLI over shared services](https://github.com/eefahd/python-clean-architecture).

## Initial design: module tree (DRAFT v4, not approved)

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
    <command_name>.py                      one small class per command (ApproveWithNote, RaiseEscalation, TurnInTask, AssignTask, ...)
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
- Walkthrough complete. Next: the recheck items in `05-recheck-items.md`, one at a time; then a redrawn tree.

### Findings behind round 4 (2026-11-23)

- fastReader (about 2,200 lines, 108 tests pass): the scanners, TOC, search and section boundaries are pure logic and reuse cleanly. Its file cache (8-character hash keys, global `~/.fastReader`, `/tmp` outputs) and file-bound `commands/*` need replacing. Section indexes depend on scanner config, so citations must use line ranges.
- quick-json-reader (one 1,030-line JS file, Apache-2.0, 25 tests pass): a Python port is low effort. Its line numbers belong to its rendered view, not the stored text, so citations must point at the stored text.
- Baseline on 29 real pages: fastReader's current HTML-to-text returned nothing on 17 of 22 HTML pages (void `meta`/`link` tags in its skip list never close), never emits headings, decodes everything as UTF-8 and turns PDFs into garbage. trafilatura (markdown mode) handled most HTML well but truncated some pages (RFC 9110 to one section) and returns nothing for PDF, text and JSON. 4 sites blocked plain HTTP behind Cloudflare.
- Extractor research (21 strategies on the same 29 pages; NOT approved, to confirm at interface time). Suggested HTML order: trafilatura (markdown; already has its own readability/jusText fallback) → readabilipy + markdownify → whole-page markdownify (never failed; keeps nav). trafilatura lost content or headings on ~6 of 20 good pages (RFC 9110, lib.ru, PostgreSQL docs, GitHub README, cpython page, Aozora). PDF: pypdf (BSD-3, license file checked) → pdfminer.six; no PDF library gave real headings. Avoid html2text (GPL), pymupdf4llm (AGPL), marker (weights limit commercial use); drop newspaper4k, goose3, justext (plain text, no headings). Text passes through; JSON pretty-printed; JSONL validated. Decoding by header charset → meta tag → charset_normalizer gave no garbled text. Possible output checks: too short (<250 chars), under half the page's visible text, heading count far below the whole page's, garbled characters. Cloudflare challenges are documented by the `cf-mitigated: challenge` header ([Cloudflare docs](https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/)). Sources and data: [trafilatura evaluation](https://trafilatura.readthedocs.io/en/latest/evaluation.html), [trafilatura external.py](https://raw.githubusercontent.com/adbar/trafilatura/master/trafilatura/external.py), [pypdf LICENSE](https://raw.githubusercontent.com/py-pdf/pypdf/main/LICENSE), [PyMuPDF about](https://pymupdf.readthedocs.io/en/latest/about.html), [marker](https://github.com/datalab-to/marker).

