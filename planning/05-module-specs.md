# Module specs

Level 5. In progress. Work runs in rounds: questions, answers, research and initial design, next questions, repeat (see `process-levels.md`).

## Round 1 decisions (user, 2026-11-23)

1. **Existing data:** fresh schema; existing data isn't migrated.
2. **Node content (researched, approved).** Nodes stay an adjacency list (`parent_id`). The node row holds title, level label, context summary and its last-verified date. Everything else (requirements, notes, research, worker responses) is content items attached to the node, each with descriptive tags (not fixed roles), its own version history and permissions. Quote pointers link a content item to a quote and a range. Sources: [tree models compared](https://dev.to/dowerdev/implementing-hierarchical-data-structures-in-postgresql-ltree-vs-adjacency-list-vs-closure-table-2jpb), [Neon ltree docs](https://neon.tech/docs/extensions/ltree). The content-item split is the agent's reasoning, not from a source.
3. **The core (researched, approved).** Ports and adapters: a new core holding all operations, with no HTTP or database code; storage behind an interface with Postgres as the implementation; FastAPI and the CLI are thin layers over the same operations; Gradio calls HTTP. Written fresh against the new schema, reusing the existing pure parts where they fit (the `permissions.py` approach, admin sessions, backups, the isolated test runner). Sources: [ports and adapters in Python](https://dev.to/elpic/hexagonal-architecture-in-python-wiring-adapters-dependency-injection-and-the-application-layer-61l), [FastAPI and CLI over shared services](https://github.com/eefahd/python-clean-architecture).

## Initial design: module list (DRAFT, not approved)

Names say what each module is or does. "Package" marks the ones that make sense as their own package; the rest are folders or files inside the app. Every module has documentation, an interface, types, a definition of done and tests.

**Core (no HTTP, no database code)**

| # | Module | Owns | Rough interface | Package? |
|---|---|---|---|---|
| 1 | Access rules | Pure permission decisions: admin, planner, worker, quote-submission credential; visibility; knowledge-base exposure | `can_<action>(principal, target) -> allowed` | yes |
| 2 | Project tree operations | Create, update, move and delete nodes; level labels; levels 1-4 linear; summary and last-verified date required on every create or update | `create_node`, `update_node`, `move_node`, `get_subtree` | no |
| 3 | Context assembly | Pure: ancestors' summaries and inherited requirements into a worker's pre-prompt | `assemble_context(ancestor_chain) -> text` | yes |
| 4 | Content items | Items attached to nodes, descriptive tags, version history, per-item write rules | `add_item`, `edit_item`, `item_history` | no |
| 5 | User quotes | Append-only quotes, pointers with ranges, validation, unapproved/approved lifecycle, supersession raising a discrepancy | `submit_quote` (quote credential only), `reference_quote`, `supersede` | no |
| 6 | Document cache | Fetching through a swappable fetcher (plain HTTP plus HTML/PDF converters), storing text and metadata, document IDs | `fetch_source(url) -> doc_id`, `source_metadata` | no |
| 7 | Document reader | Scanners adapted from fastReader, JSON reading from quick-json-reader; table of contents, get, search, get lines | `toc`, `get_section`, `search`, `get_lines(doc_id, start, end)` | yes |
| 8 | Work queue | Generic Postgres queue: enqueue, claim, complete, list | `enqueue`, `claim(kind, client)`, `complete` | yes |
| 9 | Node review | Review jobs on submission, verdicts applied, title checks (prompts adapted from SoT) | `submit_for_review`, `record_verdict` | no |
| 10 | Approval queue | Proposals, approve or approve with note (note becomes a quote), approval void if text changes | `propose`, `approve`, `reject` | no |
| 11 | Escalations | Raise (node pauses, user alerted), resolve with notes, resume with instruction | `raise_escalation`, `resolve`, `resume_task` | no |
| 12 | Task acceptance | Worker response and its "built to pass the tests" confirmation, acceptance, verification jobs, branch record, merge record | `turn_in`, `accept`, `request_verification` | no |
| 13 | Credentials | Tokens (mint, rotate, revoke with cascade), admin sessions, quote credentials | `mint`, `revoke`, `start_admin_session` | no |
| 14 | Storage port and Postgres store | Storage interface for the core; Postgres implementation; fresh schema | repository interfaces | no |

**Interfaces (thin, no business logic)**

| # | Module | Notes | Package? |
|---|---|---|---|
| 15 | HTTPS API | FastAPI routes calling the core | no |
| 16 | CLI | An HTTPS client whose commands are generated from the server's OpenAPI spec | no |
| 17 | Web UI | Gradio, an HTTP client only | yes |

**Local side (Python)**

| # | Module | Owns | Package? |
|---|---|---|---|
| 18 | Local client | Session-to-project link, prompt capture into quote submission, reviewer role pulling review jobs | yes |
| 19 | Harness adapter interface | One strict interface: capture, tools, run a headless session | inside 18 |
| 20 | Claude Code adapter | Hooks, `claude -p` review sessions (adapted from SoT) | inside 18 |
| 21 | Codex adapter | Hooks, `codex exec` review sessions | inside 18 |

**Operations (carried over)**

| # | Module | Notes |
|---|---|---|
| 22 | Live export and encrypted backups | From the existing repo |
| 23 | Isolated integration test runner | From the existing repo |

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

