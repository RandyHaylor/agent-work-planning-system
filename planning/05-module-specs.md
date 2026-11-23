# Module specs

Level 5. In progress. Work runs in rounds: questions, answers, research and initial design, next questions, repeat (see `process-levels.md`).

## Round 1 decisions (user, 2026-11-23)

1. **Existing data:** fresh schema; existing data isn't migrated.
2. **Node content (researched, approved).** Nodes stay an adjacency list (`parent_id`). The node row holds title, level label, context summary and its last-verified date. Everything else (requirements, notes, research, worker responses) is content items attached to the node, each with descriptive tags (not fixed roles), its own version history and permissions. Quote pointers link a content item to a quote and a range. Sources: [tree models compared](https://dev.to/dowerdev/implementing-hierarchical-data-structures-in-postgresql-ltree-vs-adjacency-list-vs-closure-table-2jpb), [Neon ltree docs](https://neon.tech/docs/extensions/ltree). The content-item split is the agent's reasoning, not from a source.
3. **The core (researched, approved).** Ports and adapters: a new core holding all operations, with no HTTP or database code; storage behind an interface with Postgres as the implementation; FastAPI and the CLI are thin layers over the same operations; Gradio calls HTTP. Written fresh against the new schema, reusing the existing pure parts where they fit (the `permissions.py` approach, admin sessions, backups, the isolated test runner). Sources: [ports and adapters in Python](https://dev.to/elpic/hexagonal-architecture-in-python-wiring-adapters-dependency-injection-and-the-application-layer-61l), [FastAPI and CLI over shared services](https://github.com/eefahd/python-clean-architecture).

## Initial design: module list (DRAFT v3, not approved)

**Module** means a normal code module: a cohesive unit with a clear responsibility and an interface, often small (a single file of helpers, one strategy implementation, or a small folder). Modules can be broken down into task-sized work. Earlier drafts (v1, v2) listed subsystem-sized boxes instead of modules; v3 lists actual modules, grouped by area. **Every row is a module. The headings are only groupings for reading; they are not modules.**

Every module has documentation, an interface, types, a definition of done and tests. Paths are proposals. "(carried)" means adapted from the existing repo; "(SoT)", "(fastReader)", "(quick-json-reader)" mean adapted from that repo.

### Access and identity
| Module | Responsibility | Interface |
|---|---|---|
| `access/principal_types.py` | Principal and role types: admin, planner, worker, quote submitter | types |
| `access/permission_policy.py` (carried) | Pure permission decisions, visibility, knowledge-base exposure | `can_<action>(principal, target)` |
| `authentication/password_hashing.py` (carried) | Hashing and checking the admin password | `hash_password`, `check_password` |
| `authentication/admin_sessions.py` (carried) | In-memory admin sessions from the browser login | `start`, `lookup`, `end` |
| `authentication/token_hashing.py` (carried) | Hashing bearer tokens for lookup | `hash_token` |
| `authentication/token_lifecycle.py` | Mint, rotate, revoke with cascade, including quote-submission credentials | `mint`, `rotate`, `revoke` |
| `authentication/credential_resolution.py` | Turning a request's credential into a principal | `principal_for(credential)` |

### Project tree
| Module | Responsibility | Interface |
|---|---|---|
| `tree/node_types.py` | Node, content, node state and level-label types | types |
| `tree/level_placement_rules.py` | Pure: levels 1-4 one node each in a line; where a node may go | `check_placement(parent, node)` |
| `tree/node_operations.py` | Create, update, move, delete; summary and last-verified date required on every create or update | `create_node`, `update_node`, `move_node`, `delete_node` |
| `tree/node_content_operations.py` | Adding and editing content on a node, with version history | `add_content`, `edit_content`, `content_history` |
| `tree/node_claiming.py` | Safely claiming a node for one client | `claim_node`, `release_node` |
| `tree/node_state_views.py` | Read-only views of nodes by state ("queues") | `list_by_state` |
| `tree/tree_storage_port.py` | The storage interface the tree modules use | protocol |

### Context
| Module | Responsibility | Interface |
|---|---|---|
| `context/context_assembly.py` | Pure: ancestor summaries and inherited requirements into a pre-prompt | `assemble_context(ancestor_chain)` |

### User quotes
| Module | Responsibility | Interface |
|---|---|---|
| `quotes/quote_types.py` | Quote, pointer and range types | types |
| `quotes/quote_pointer_validation.py` (SoT) | Pure: pointer ranges are valid and continuous | `validate(pointers, quotes)` |
| `quotes/quote_text_resolution.py` (SoT) | Resolving a pointer to its exact text | `resolve(pointer)` |
| `quotes/quote_supersession.py` | Supersession links and marking superseded quotes | `supersede`, `superseded_by` |
| `quotes/approved_text_binding.py` | An approval is valid only for the exact text shown; any edit voids it | `bind(text)`, `still_valid(binding, text)` |
| `quotes/quote_storage_port.py` | Storage interface for quotes | protocol |

### Grouping: fetching
| Module | Responsibility | Interface |
|---|---|---|
| `fetching/source_fetcher_interface.py` | The fetch strategy interface | protocol |
| `fetching/http_source_fetcher.py` (fastReader `web.py`) | Plain HTTP fetch | implements the interface |
| `fetching/html_to_text.py` (fastReader) | HTML to text | `html_to_text(html)` |
| `fetching/pdf_to_text.py` | PDF to text | `pdf_to_text(bytes)` |

### Grouping: sources and citation
| Module | Responsibility | Interface |
|---|---|---|
| `sources/source_registry.py` | Cached-source records: ID, origin, date cached, re-check flag | `register_source`, `source_metadata` |
| `sources/document_citation.py` | Citing by document ID and line range; rendering the quoted text | `cite`, `resolve` |
| `sources/source_storage_port.py` | Storage interface for sources | protocol |

### Document reader (pure over text)
| Module | Responsibility | Interface |
|---|---|---|
| `reader/structure_marker_types.py` (fastReader) | Marker and manifest types | types |
| `reader/heading_scanner.py` (fastReader) | Chapter, section, page and block markers | `scan(text)` |
| `reader/indent_depth_scanner.py` (fastReader) | Indentation-depth markers | `scan(text)` |
| `reader/bracket_depth_scanner.py` (fastReader) | JSON bracket-depth markers | `scan(text)` |
| `reader/tag_depth_scanner.py` (fastReader) | HTML/XML tag-depth markers | `scan(text)` |
| `reader/table_of_contents.py` (fastReader) | Table of contents from markers | `toc(manifest, options)` |
| `reader/section_extraction.py` (fastReader) | Getting one section | `get_section(text, manifest, marker)` |
| `reader/text_search.py` (fastReader) | Search with container context | `search(text, manifest, query)` |
| `reader/line_slicing.py` | Getting lines by range | `get_lines(text, start, end)` |
| `reader/json_reader.py` (quick-json-reader) | JSON search, exclude, prune, render | `read_json(value, options)` |

**Review is not a code area.** A review is an ordinary task: a reviewer client claims the review node, gets standard review instructions (configuration text adapted from SoT, including title checks), and turns in its verdict as its response. Submitting for review and recording a verdict are command classes.

### Grouping: commands (command pattern, OOP)
| Module | Responsibility |
|---|---|
| `commands/request_authorizer.py` | Turns a credential into a principal and asks the permission policy whether it may run a command |
| `commands/unit_of_work.py` | Runs one command's changes in a single transaction |
| `commands/<command_name>.py` | One small class per command (e.g. `ApproveWithNote`, `RaiseEscalation`, `TurnInTask`, `ClaimReviewNode`), composing the single-job classes it needs |

Node state is a plain attribute on the node; who may change it to what is a rule in the permission policy. No subject-grouped operations modules.

### Storage (Postgres)
| Module | Responsibility |
|---|---|
| `storage/schema.sql` | Fresh schema, version triggers |
| `storage/database_connection.py` (carried) | Connections and transactions |
| `storage/postgres_tree_store.py` | Implements the tree storage port |
| `storage/postgres_quote_store.py` | Implements the quote storage port |
| `storage/postgres_source_store.py` | Implements the source storage port |
| `storage/postgres_credential_store.py` | Token and credential records |

### HTTPS API
| Module | Responsibility |
|---|---|
| `http_api/application.py` | FastAPI app wiring, TLS (carried) |
| `http_api/credential_dependency.py` | Resolving the request's principal |
| `http_api/command_routes.py` | Maps each route to its command class |
| `http_api/error_mapping.py` | Operation errors to HTTP status codes |

### CLI (HTTPS client)
| Module | Responsibility |
|---|---|
| `cli/api_client.py` | Calling the HTTPS API with a credential |
| `cli/openapi_command_generator.py` | Building commands from the server's OpenAPI spec |
| `cli/entry_point.py` | Command-line entry |

### Web UI (Gradio, HTTPS client, no logic)
| Module | Responsibility |
|---|---|
| `web_ui/gradio_application.py` | App and page wiring |
| `web_ui/tree_view_page.py` | Viewing the tree, adding addendums |
| `web_ui/approval_page.py` | The approval view |
| `web_ui/escalation_page.py` | The escalation view |
| (uses `cli/api_client.py` or a shared client package) | |

### Local client (Python)
| Module | Responsibility |
|---|---|
| `local_client/client_configuration.py` | Server address, quote credential, reviewer settings |
| `local_client/session_project_link.py` | Linking a harness session to a project |
| `local_client/prompt_capture.py` (SoT) | Captured prompt plus context range into a quote submission |
| `local_client/transcript_context_reader.py` (SoT) | Reading the preceding agent text from a transcript |
| `local_client/reviewer_loop.py` | Claiming review nodes and running reviews through an adapter |
| `local_client/harness_adapter_interface.py` (SoT) | The adapter interface |
| `adapters/claude_code/hook_entry.py` (SoT) | Claude Code hooks into prompt capture |
| `adapters/claude_code/headless_session.py` (SoT) | `claude -p` sessions |
| `adapters/codex/hook_entry.py` | Codex hooks into prompt capture |
| `adapters/codex/headless_session.py` | `codex exec` sessions |

### Operations (carried)
| Module | Responsibility |
|---|---|
| `operations_tooling/live_export.py` (carried) | Readable mirror of each project |
| `operations_tooling/encrypted_backup.py` (carried) | Encrypted full backups and restore |
| `operations_tooling/bootstrap.py` (carried) | First-time setup |

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

