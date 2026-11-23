# High-level plan

Level 3. Approved by the user on 2026-11-23. User: "otherwise yes thi sis sounding good"

## General approach

1. **One core, thin interfaces.** All operations, including user actions, live in a core that knows nothing about HTTP. HTTP, the CLI and the Gradio UI are thin layers over that core, so each one can do everything and none of them holds business logic. (DoD 13, 17, 18)
   - Today `app.py` (777 lines) mixes routes, SQL and HTTP errors in each function, with no service layer. The first step is pulling the operations out of it.
   - What already separates cleanly: `permissions.py` (pure), the admin session store, the backup renderer, encrypted backups, the version trigger, and the isolated test runner.
2. **Storage behind an interface.** The core talks to a storage interface, and Postgres is the one implementation. Copied-in tools that use files today get the same treatment.
3. **Adapt the other tools into the planning system, never modify their repos.** See "Adapting the other tools into the planning system" below.
4. **Build it with its own process.** The plan docs in `planning/` serve as the tree until the server can hold them.

## Conceptual pieces

Each piece is conceptual and will not be split into nodes. Modules come later, at level 5, and need not match these pieces.

| Piece | What it covers | Definition of done (piece level) |
|---|---|---|
| Project tree | One generic node type, level labels, requirements on the node they govern, requirement inheritance, context summaries assembled top-down; the planner who creates a node writes its summary, and the summary is updated whenever the node is created or updated, at least its last-verified date | A project runs through all levels in one tree; any node can export its assembled context; no node is created or updated without its summary being updated |
| Access | Roles, tokens, admin session, visibility, knowledge bases, cascading revocation (carried over); admin login that also works from the CLI and MCP | Every rule enforced in the core, the same through every interface |
| User quotes | Capture from the real conversation by the local client; agents can only point at quotes; quote lifecycle and supersession; agents without prompt capture (web chats, unsupported CLIs or apps) are allowed only with the user's approval, forgo guaranteed user quotes, and can still use the web approval queue, where the user's approvals and notes become quotes | No path lets an agent create or edit a quote |
| Document quotes | The service fetches, caches and logs sources; agents read through a reader and cite by document ID and line range; the server renders the text | No path lets an agent see the cache or supply quote text |
| Queues | Reviews, proposals awaiting approval and escalations are ordinary nodes or content in the one tree; "queues" are views of nodes by state, and clients claim nodes (refined at level 5) | Each view's items can be listed, acted on and resolved through every interface |
| Task work and acceptance | Workers turn in responses only; tests decide acceptance; outside verification for deep modules; escalation and resume; the planner merges each task's work on acceptance | A worker's permissions can't touch its task, tests or definition of done |
| Interfaces | HTTP, CLI with the same interface, Gradio UI; no separate MCP server, instead a permission level lets an agent act as the user over HTTPS (refined at level 5) | Any action through one interface is possible through all |
| Local client and harness adapters | Generic client, plus Claude Code and Codex adapters for capture, tools, review sessions | Both harnesses capture quotes and run reviews |
| Operations | Backups, live export, running on the host, web exposure for testing (Cloudflare or similar) | Carried-over behaviour works; web agents can reach it in a test |

**Carried up from level 4** (user, 2026-11-23):
- Context summaries: "1 yes, and these summaries also must be updated when nodes change, even if only to update the last verified date on it. In fact that is required when a node is created or updated."
- Merging: the planner merges on acceptance (user's answer).
- Agents without prompt capture: "the user must approve the use of agents (web or unsupported cli/app) that cannot support the user prompt capturing transcript hooks, etc. These are the same situation." and "remember to include that thoes agents CAN still use the web gui based approval system for users"

## Adapting the other tools into the planning system

The agent planning system is the base. SoT, fastReader and quick-json-reader are not brought in as they are: we build versions of what they do that work inside the planning system, on its Postgres storage, its authentication and its permissions. Their code and designs are reused wherever they fit. User: "we're meant to be adapting sot/fast reader in - not just bringing them in as is, building versions that work for us into the agent planning system to build what we need."

| Tool | What it is (from the survey) | What we build from it |
|---|---|---|
| source-of-truth | Python, stdlib only, ~5,400 lines; JSON files; quotes captured by a `UserPromptSubmit` hook, append-only; nodes hold only pointers to quotes, checked by a validator; title review; `claude -p` reviewer adapter | User quotes and their lifecycle, quote pointers and validation, title review and node review, all stored in Postgres and governed by the planning system's tokens and roles. Its quote capture becomes the local client's job; its reviewer becomes a reviewer client fed by the queue |
| fastReader | Python, stdlib only, ~2,000 lines; four structural scanners; content-hash cache | The document cache and reader: sources stored in Postgres, read through the scanners, cited by document ID and line range, served through the planning system's interfaces |
| quick-json-reader | JavaScript, one source file (`src/quick_json_reader.js`) plus tests and a web UI ([repo](https://github.com/RandyHaylor/quick-json-reader)) | JSON reading for the document reader, built from its source. Whether that means a Python version or running the JavaScript is a level 5 decision |

**Special key.** The planning system already has a full authentication system (role-scoped tokens, enforced server-side). The special key is built on it: a credential, held only by the local client, that is the only thing allowed to submit user quotes.

## Choosing modules at level 5

Modules are chosen with the user involved, using good judgement to separate functionality into clean modules with good professional separation. User: "I say we just include a list of different accepted approaches like that, and specify that user should be involved, and use good judgement to separate out functionality into clean movules iwth good professional separation."

Each module has clear documentation, an interface, types, a definition of done and tests (see Repo layout below).

Module separations MUST be chosen for good software architecture and encapsulation, NOT necessarily by subject matter or by upstream lists of project needs (user, at level 5). Prioritize good, proven software engineering patterns (strategy, adapter, facade, factory, etc.), but not for their own sake: only where they add efficiency and value and reduce or encapsulate complexity (user, at level 5).

**Accepted approaches** (guidance for judgement, not operating restrictions):
- **Information hiding.** A module hides a design decision, especially one likely to change. ([Parnas 1972](https://www.cse.sc.edu/~mgv/csce590f20/ParnasCriteria.pdf))
- **Deep modules.** A simple interface with substantial functionality behind it. ([Ousterhout lecture](https://web.stanford.edu/~ouster/cgi-bin/cs190-spring16/lecture.php?topic=modularDesign))
- **Agent-sized work.** About one pull request per agent session; an agent contradicting itself is a sign the chunk is too big. ([arXiv 2512.12216](https://arxiv.org/pdf/2512.12216), [harness playbook](https://lipingtababa.github.io/harness-engineering-playbook/en/chapters/04b-task-decomposition.html))
- **Declared ownership.** Each module names the operations and types it owns, with shared types at clear seams. ([AECP](https://arxiv.org/pdf/2610.06481))

## Repo layout

One repo. A module is a unit of work with a clean interface, and it is not always a package. A module becomes its own installable package only when that makes sense; otherwise it can be a folder, a file or an interface inside the app, so work can still be split neatly by interface or file. Every module, package or not, has clear documentation, an interface, types, a definition of done and tests. A non-package module that doesn't make sense to integration-test on its own can rely on unit tests. User: "even if a module is not a package, it STILL needs clear documentation and testing. some non-pacakage modules may not really make sense for independent integration testing and unit testing will be sufficient." User: "I'd like the ability to specify 'modules' as maybe not always being 'packages' per se - only when tha tmakes sense. it might prevent us from splitting up work neatly by interface/file/etc otherwise." Where a module reuses code from SoT, fastReader or quick-json-reader, it notes the source repo and commit.

## Deferred to level 5

- quick-json-reader: a Python version or running the JavaScript. User: "yes that works in this case"
