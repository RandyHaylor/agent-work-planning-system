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
      node_claimer.py                      one client per node
      node_state_views.py                  read-only views by state ("queues")
      tree_storage_port.py
    context_assembly/                      public: ContextAssembler
      context_assembler.py                 ancestor summaries + inherited requirements -> pre-prompt
    user_quotes/                           public: QuoteLedger (facade), quote types, QuoteStoragePort
      quote.py                             quote, pointer, range types
      pointer_validator.py (SoT)
      quote_text_resolver.py (SoT)
      supersession_linker.py
      approved_text_binder.py              approval valid only for the exact text shown
      quote_storage_port.py
    document_sources/                      public: SourceLibrary (facade), SourceStoragePort
      source_registry.py                   ID, origin, date cached, re-check flag
      document_citation.py                 cite by ID + lines; server renders text
      source_storage_port.py
      fetching/                            public: SourceFetcher
        source_fetcher.py                  strategy interface
        http_source_fetcher.py (fastReader web.py)
        converters/                        public: ConverterFactory
          converter_factory.py             picks a converter by content type
          html_to_text.py (fastReader)
          pdf_to_text.py
  document_reader/                         own package, pure over text; public: DocumentReader (facade)
    structure_markers.py (fastReader)
    scanners/                              strategies, one per structure kind (fastReader)
      heading_scanner.py
      indent_depth_scanner.py
      bracket_depth_scanner.py
      tag_depth_scanner.py
    table_of_contents.py (fastReader)
    section_extraction.py (fastReader)
    text_search.py (fastReader)
    line_slicing.py
    json_reading/                          (quick-json-reader)
  commands/                                public: CommandRunner
    command_runner.py                      authorize -> unit of work -> run command
    request_authorizer.py
    unit_of_work.py
    <command_name>.py                      one small class per command (ApproveWithNote, RaiseEscalation, TurnInTask, ClaimReviewNode, ...)
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
  reviewer_loop.py                         claims review nodes, runs them through an adapter
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

**Review is not a code area.** A review is an ordinary task: a reviewer client claims the review node, gets standard review instructions (configuration text adapted from SoT, including title checks), and turns in its verdict as its response. Submitting for review and recording a verdict are command classes.

Node state is a plain attribute on the node; who may change it to what is a rule in the permission policy.

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

