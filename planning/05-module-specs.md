# Module specs

Level 5. In progress. Work runs in rounds: questions, answers, research and initial design, next questions, repeat (see `process-levels.md`).

## Round 1 decisions (user, 2026-11-23)

1. **Existing data:** fresh schema; existing data isn't migrated.
2. **Node content (researched, approved).** Nodes stay an adjacency list (`parent_id`). The node row holds title, level label, context summary and its last-verified date. Everything else (requirements, notes, research, worker responses) is content items attached to the node, each with descriptive tags (not fixed roles), its own version history and permissions. Quote pointers link a content item to a quote and a range. Sources: [tree models compared](https://dev.to/dowerdev/implementing-hierarchical-data-structures-in-postgresql-ltree-vs-adjacency-list-vs-closure-table-2jpb), [Neon ltree docs](https://neon.tech/docs/extensions/ltree). The content-item split is the agent's reasoning, not from a source.
3. **The core (researched, approved).** Ports and adapters: a new core holding all operations, with no HTTP or database code; storage behind an interface with Postgres as the implementation; FastAPI and the CLI are thin layers over the same operations; Gradio calls HTTP. Written fresh against the new schema, reusing the existing pure parts where they fit (the `permissions.py` approach, admin sessions, backups, the isolated test runner). Sources: [ports and adapters in Python](https://dev.to/elpic/hexagonal-architecture-in-python-wiring-adapters-dependency-injection-and-the-application-layer-61l), [FastAPI and CLI over shared services](https://github.com/eefahd/python-clean-architecture).

## Initial design: module list (DRAFT v2, not approved)

**Why v2.** The first draft grouped work by data and features ("content items", "approval queue", "escalations", "task acceptance"), which produces chunks of work, not modules. User: "they need to be modules separated logically not just 'groupings of stuff'." v2 was reworked with good judgement, using the accepted approaches in `03-high-level-plan.md`, so modules are separated logically rather than grouped by data or features.

Every module has documentation, an interface, types, a definition of done and tests. "Package" marks the ones that make sense as their own package.

| # | Module | What it's responsible for | Rough interface | Package? |
|---|---|---|---|---|
| 1 | Access rules | Who may do what: the permission policy for admin, planner, worker and the quote-submission credential; visibility; knowledge-base exposure. Pure, no I/O | `can_<action>(principal, target)` | yes |
| 2 | Authentication | How identity is proven: token hashing, minting, rotation, revocation cascade, admin sessions, quote credentials | `authenticate(request_credential) -> principal`, `mint`, `revoke` | no |
| 3 | Project tree | The tree's invariants: one generic node type and its content, levels 1-4 linear, summary and last-verified date on every create or update, moves, content version history, node states, and safe claiming of a node by a client (so two reviewers never take the same one). Reviews, escalations and proposals are ordinary nodes or content; "queues" are read-only views of nodes by state | `create_node`, `update_node`, `move_node`, `add_content`, `get_subtree`, `claim_node`, `list_by_state` | no |
| 4 | Context assembly | How a worker's pre-prompt is composed from ancestor summaries and inherited requirements. Pure | `assemble_context(ancestor_chain) -> text` | yes |
| 5 | User quotes | Quote integrity: append-only storage, pointers with ranges, resolving quote text, validation, supersession links, approval tied to the exact text shown | `submit_quote`, `resolve(pointer)`, `validate(pointers)`, `supersede` | no |
| 6 | Source fetcher | How a URL becomes text: plain HTTP plus HTML/PDF converters, behind a swappable strategy | `fetch(url) -> text, metadata` | yes |
| 7 | Document reader | How text's structure is found and read: scanners (from fastReader), JSON reading (from quick-json-reader), get lines. Pure over text | `toc`, `get_section`, `search`, `get_lines` | yes |
| 8 | Document sources | Document quotes: the registry of cached sources (document ID, origin URL, date cached, whether to re-check), pointers citing a document by ID and line range, and rendering the quoted text server-side | `register_source`, `cite(doc_id, start, end)`, `resolve(pointer)` | no |
| 9 | Review criteria | How a node is judged against its quotes: building the review prompt, parsing the verdict, title checks (adapted from SoT). Pure | `build_review_prompt(node, quotes)`, `parse_verdict(text)` | yes |
| 10 | Storage | That storage is Postgres: fresh schema, migrations, and the implementations of the storage interfaces the other modules declare | per-module repository interfaces | no |
| 11 | System operations | The use cases that combine the modules, such as "worker turns in a task" (check access, record response, pause or accept) or "user approves with a note" (record approval, create quote). The one API every interface calls | one function per operation | no |
| 12 | HTTPS API | The protocol: FastAPI routes mapping requests to system operations; the OpenAPI spec | routes | no |
| 13 | CLI | Command-line presentation, generated from the OpenAPI spec; an HTTPS client | commands | no |
| 14 | Web UI | Gradio presentation; an HTTPS client; no logic | pages | yes |
| 15 | Local client | Local-side behaviour: linking a session to a project, turning captured prompts into quote submissions, acting as a reviewer by claiming review nodes; holds the quote credential; defines the harness adapter interface | `capture`, `run_reviewer` | yes |
| 16 | Claude Code adapter | Claude Code specifics: hooks, `claude -p` sessions | implements the adapter interface | inside 15 |
| 17 | Codex adapter | Codex specifics: hooks, `codex exec` sessions | implements the adapter interface | inside 15 |
| 18 | Backups and export | Carried over: encrypted full backups and the readable live export | existing commands | no |

**Folded in, and why**
- Content items into the project tree: a node and its content are one thing.
- No separate queue. Reviews, escalations and proposals are ordinary nodes or content in the one tree; "queues" are views of nodes by state, and clients claim nodes. User, on a separate queue with job kinds: "this seems more like subject separation vs function separation. odd module separation. the nodes also need to be interchangeable across, right? why would we plan for nodes ot have different types" and "yes I kind of assumed it was like that all along."
- Approval: user quotes (approval valid only for the exact text) plus system operations (the approve use case).
- Escalations: content on the node that raised it, the node's paused state, and system operations (raise, resolve, resume).
- Verification is assigned by the planner like any task.
- Document quotes got their own module (Document sources), a gap found during review.
- Task acceptance into system operations: it's a use case, not a hidden decision.
- The document cache split into the source fetcher (how text is obtained) and storage (where it's kept).
- The isolated integration test runner is development tooling, not part of the system.

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

