# Agent Planning System: Plan

Nov 22, 2026 · @Randy Haylor

The agent planning system grows into one harness-agnostic system, built on a Postgres server, that enforces top-down documentation backed by real quotes from the user, the web, documentation and code. The process itself is described in the Philosophy doc.

## The win

An hour or two of real-time planning lets agents work for hours on their own without drifting. Coding becomes the easy part, and the human manages instead of babysitting.

- Specs rest on real quotes and real technical references.
- Interfaces and tests are real, built, and walked through before coding starts.
- Agents work unhindered on validated, trustworthy structure. No more all-day fix-and-tweak thrashing.

## Visible wins

These three wins are the product's headline.

1. **No drift on user scope.** Every requirement traces back to the user's own words or their explicit confirmation.
2. **No drift on references and research.** Every technical claim traces back to a cached source.
3. **Every quote comes from the system's own cache.** The service fetches and caches each source and serves the quote, so the quoted words are guaranteed to be in the cited source. AI often misquotes even after reading a source and citing it, and this design rules that out from the start.

## Process

The process is the system's documentation, and following it means building wiki nodes.

- **One Philosophy doc** describes the process, and also works as the reference for following it without tools.
- **The process is the deliverable.** Review in this version is light: it checks that each quote matches its claim, without running code or anything complex. The process makes clear that an end result reached without the process counts as a failure.
- **All levels, every time.** Every request that uses the process goes through all the levels. Simple, immediate requests that stand on their own don't need the process; spikes or research relevant to a project belong in that project.
- **Walkthroughs before scaffolding.** Once the modules are identified, step-by-step use-case walkthroughs and user stories refine the design.
- **Findings move back up, without halting.** Finish what's possible at the current level, carry the issue list up to the level that has to address it, then work back down updating each level.
- **Nothing enters the plan without explicit approval.** Proposals go to the user as a list, and only items the user explicitly approves are added to a formal planning doc. This applies to this plan and to the system being built.
- **Repo layout is decided per project,** based on size and context.

## End to end

Requirements, research and documentation all rest on real quotes. The plan is built top-down until it's broken into assigned task nodes.

1. Build requirements from real user quotes.
2. Prove research and documentation with real quotes from sources.
3. Build top-down: what we're doing, the definition of done, the high-level plan, walkthroughs, then the modules.
4. Build the module scaffolding and integration tests.
5. Assign task nodes, and break them down further.

## Node tree

There is one tree and one generic kind of node. The Postgres server is its platform.

- **The tree is the project.** Levels 1 to 4 (what we're doing, definition of done, high-level plan, walkthroughs) are one node each in a straight line; branching starts at module specs. A node can carry a level label, but every node is the same type.
- **Requirements live on the node they govern,** with the user's words beside them, and always pass down to every node below. They never sit in a separate branch.
- **Spikes** are task nodes allowed at any layer, visible at that layer. Their findings don't pass down by default.
- **Storage.** Each project's tree is basically one large Postgres table.
- **Titles stay generic.** A title names a topic and makes no claim. SoT's title checks are kept.
- **The wiki is the documentation.** The user can view the whole tree, including requirements and agent project notes, through a small Gradio app on the wiki website, and add addendums. It becomes the documentation for what was built.
- **Admin layer.** The agent planning system's top-level admin manages knowledge bases (or links to them), permissions and task assignment.
- **Control by scope.** An agent sees only its own task and can't edit it. The only thing it can do is turn in a response on its task node.
- **Tests decide acceptance.** Integration tests are built when task nodes are created, and they pass against mocks: hollow shells, like the first step of TDD. Work that doesn't pass isn't accepted.
- **History.** Submitted items stay on the server as history. Agents using the HTTPS interface can query their status.

## Context tree

A major feature: every agent automatically gets the story of what's being built, assembled from the nodes above its task.

- **Every node has a context summary** it can export, safe to pass down to any level.
- **Summaries add, never repeat.** The top node's summary covers the project: the mission, goal, or what the user wants. Each node below adds only what it contributes beyond its ancestors. For example, a UI node adds UI details, and a React CSS design node under it adds what it has.
- **Assembled automatically.** Adding up the summaries from the top node down to a work node gives a ready-made pre-prompt that tells the agent what's being built. It runs from generic at the top to specific at the task.
- **Given by default,** because agents are always helped by knowing the story.
- **Extendable.** Agents building nodes can add more information, knowledge base access, or access to other nodes where needed.

## Roles and permissions

The agent planning system's roles, permission tiers and multi-knowledge-base support carry over.

- **Roles.** Admin, planner and worker, each with its own permission tier.
- **Admin and planner agents decide what worker agents can see.**
- **Knowledge bases.** Multiple knowledge bases are supported, and each agent is given access to the ones it should see.
- **Other projects.** Agents can optionally be given read-only access to other projects, when that context is relevant.
- **Restrictions are enforced** through each agent's access, not just through instructions.

From the agent planning system ([repo](https://github.com/RandyHaylor/agent-work-planning-system)):

|  | Admin | Planner | Worker |
| --- | --- | --- | --- |
| Access | Browser login session, approved by the user each session | Token scoped to a whole workorder; acts as the workorder's admin | Token scoped to its own subtree |
| Read | Everything | Own workorder; other workorders that are visible or granted; every KB | Its subtree; ancestor environment docs; KBs assigned to its workorder or node |
| Write | Anywhere, including KBs | Any doc in own workorder | Report, spike, escalation and KB-proposal docs in its subtree; edits only docs it wrote |
| Manage | Hide workorders, grant visibility, resolve KB proposals | Mint worker tokens, set state, answer escalations, assign KBs | Nothing |

- **Visibility.** Other workorders return "not found" to workers. Planners see other workorders only if they're visible or explicitly granted.
- **Version history.** Every edit to a doc keeps the previous version, append-only, as an audit trail.
- **Cascading revocation.** Revoking a token also revokes every token minted beneath it.
- **Depth limit.** Applies to breaking a module's task into smaller tasks, about four levels deep. It doesn't apply to the planning layers above, which go deeper but are often linear, with one child per layer.

## Quotes

Quotes are absolute truth, because the system generates them from real input. Agents never create or edit them, and quotes are never reviewed.

**User quotes**

- **Local capture.** The local client keeps a transcript of the whole conversation, without tool-call contents or document edits. Tool calls appear only as breadcrumbs, such as "read X document", never their contents or image data.
- **Confirmation in conversation.** The default, as in SoT today, is to propose in the conversation ("I propose X, is that okay?") and cite the user's "yes". An agent never creates an unquoted node because it wants something.
- **Referencing a quote.** A local agent says through the interface that it's using a quote. The client reads the quote in code; the agent never sees or controls it. The quote's ID is created locally and becomes its server ID.
- **Context.** The agent chooses how much text above the user's response to include, from none to as much as it wants. It has to be one continuous range ending at the response, with no gaps, probably specified by line.
- **Pushed when referenced.** Only quotes that get referenced are pushed to the server, with metadata such as date, session ID and origin, so anyone can judge whether one is outdated. Everything else stays in the local cache.
- **Special key.** Only the local client holds the key that lets it submit a user response. That guarantees a real transcript quote, not something an LLM interpreted or generated.
- **Shared.** Any agent connected over HTTPS can see and reference user quotes already on the server.
- **What a user quote proves.** Only what the user said. A document read or mentioned in the quoted stretch proves nothing on its own.

**Document quotes**

- **The service owns the cache.** Agents never cache anything. To quote a page, an agent visits the URL through the service, which fetches it, caches it and logs the URL. The agent reads it through a fastReader-style interface built into the app.
- **Agents never see or touch the cache,** so quotes are safe from hallucination, tampering and inference. An agent may say "I inferred X because of this source, and here's the quote", never "I read this, so X".
- **Cached sources belong to the project.** Each records its source, the date it was cached, and whether the original has to be re-checked. The cached copy is the default.
- **Document quotes come from the server.** A node cites a document by ID and line. The server renders the quoted text and supplies the metadata; the agent building the node never does either.

**Quote lifecycle**

- **Unapproved quotes** stay on the server but can't be cited in a node. The agent that submitted one can delete it.
- **Approved quotes** are historical, and no agent can delete them.
- **Supersession.** A new quote can list older quotes it supersedes. A node citing a superseded quote shows it marked as superseded, next to the new quote. Supersession raises a top-level user task, such as "discrepancy detected, review required". Resolving it isn't automated.

## Approval queue

The wiki website has a queue where the user approves proposals directly on the server. This closes the validation gap for web clients.

- The queue is for web agents, or for local agents only when the user asks to review a batch of items in the wiki.
- Every proposal reaches the server through the same interface. If it includes a user response, it's a user quote. If it doesn't, it waits in the queue.
- The user logs in and approves, or approves with a note. A note counts as a user quote that can be cited.
- The quote is the proposal plus the user's acceptance. It's valid only for the exact text the user saw. Any edit to that text invalidates the approval.
- Web agents can reference quotes already on the server, but can't add new user quotes.

## Review

Nodes are reviewed, never quotes. Reviews are run by designated reviewer clients, never by the agents doing the work.

- **What's checked.** Specifications and user decisions need a user quote. Technical claims need a reference quote that corroborates them. A node's claim has to match its quote and add nothing the user didn't approve. A node that relies on a document needs a document quote, or it's rejected.
- **Async.** As in SoT today, review never blocks the agent. It's told the node was submitted for review, not that it was approved, and the result comes back when the review is done.
- **Review queue.** The server holds a generic review task queue and sends jobs to reviewer clients that are available and assigned. Any client can be set up in a reviewer role, as part of the server system.
- **Sessions.** Reviewer clients run review sessions through their harness adapters, using command-line session control such as `claude -p`.

## Building and verifying modules

A building agent's job is to pass its module's integration tests. An outside agent then verifies the work against the original tests.

- **The tests are the job.** Building agents know they must build to pass the integration tests. They can't change the tests or the definition of done.
- **Submission.** When a building agent submits its node, one field confirms it built the module to pass the test.
- **Permissions.** Enforced by the system, not just instructions. A building agent's auth token won't let it change its task, tests or definition of done. It can only add notes in child nodes and fill in its own response fields.
- **Verification tasks.** For deep modules, and anything else that has to work, an outside agent gets the original, unmodified tests and the definition of done. It runs the code against the tests, uses its own judgment, decides pass or fail, and reports back.
- **Failed verification.** For now, a deep module that fails verification escalates as a user review event.
- **When the spec can't be met.** A building agent that finds it can't meet the interface, tests or definition of done keeps going with whatever it can still meet, to surface any other issues. It doesn't just stop. It finishes as much as it can within the rules, so there's all the information needed for potential changes, then escalates the issues and turns in its work, rather than sending it to review. The agent is then done, and the node pauses: nothing more happens on it until the user handles the escalation. Higher levels of the tree, or at least that node, will need revisiting.

## Interfaces and harnesses

HTTPS is the one interface, and everything harness-specific lives in adapters.

- **CLI adapter.** It exposes the exact same interface as HTTPS, so an agent running locally can use it simply.
- **Local harness client.** It sits outside the HTTPS interface to the Postgres server, is platform- and harness-independent, and has one strict generic interface. Adapters for Claude, Codex, Pi and later harnesses hold all custom code: tools for agents, transcript capture, delivering review results, and session control for reviews.
- **Native ask-question tools** in Claude Code and Codex are supported through adapters.

* **Stands on its own.** The system works well without any particular harness, and expects harnesses of varied sophistication: Claude Code CLI, Codex CLI, the desktop apps, web harnesses, or custom systems such as Unharness, which gives smaller and local models detailed, step-by-step support.

## Task assignment and isolation

Mainstream harnesses already have what's needed to start agents on tasks. This approach already works well in the agent planning system.

- **Assignment.** With a mainstream harness such as the Claude CLI, the primary agent sees a task to assign, spins up an agent, and gives it the access it needs to start on that task.
- **Isolation is the user's choice.** The user and the primary agent are responsible for keeping each agent in its own lane. The system recommends best practices but doesn't enforce them.
- **Recommended practices.** Give each agent its own branch or git worktree. Use a local git copy of the real project, so agents get access only to that local repo. Give agents their own sandbox. The user chooses how far to strengthen isolation.

## Modules

The agent planning system repo is the base. It's iterated to bring in features from SoT, fastReader and the JSON reader.

- **Build on the agent planning system.** Its repo is the scaffold to iterate. The SoT repo stays as it is for now.
- **Extreme modularity.** Every module has clear documentation, an interface, types, a definition of done and tests. A module is its own package only when that makes sense; a non-package module that doesn't make sense to integration-test on its own can rely on unit tests. Mocked passing tests come before development.
- **Modules are consumed as dependencies.** The finished product pulls them in seamlessly. External integrations are wrapped in generic strategy-style wrappers.
- **Adapt, don't modify.** fastReader and quick-json-reader are copied in and adapted. Their original repos stay untouched.

## Harness support

Prompt capture is verified for the Claude CLI and Codex CLI. The other platforms still need spikes.

| Platform | Prompt capture | Status |
| --- | --- | --- |
| Claude Code CLI | `UserPromptSubmit` hook | Working today in SoT |
| Codex CLI | `UserPromptSubmit` hook, receives `prompt` and `transcript_path`; "Hooks are enabled by default" ([docs](https://learn.chatgpt.com/docs/hooks)) | Verified in docs; the transcript format "isn't a stable interface" |
| Codex desktop | Hooks reviewed under Settings > Hooks ([docs](https://learn.chatgpt.com/docs/hooks)) | Needs a spike |
| Claude desktop (Windows, Mac, Linux beta) | Runs the Claude Code engine; Linux beta on Ubuntu 22.04+ and Debian 12+ ([docs](https://code.claude.com/docs/en/desktop-linux)) | Hook behavior unverified; needs a spike |
| Web chats | None. Share links are snapshots only the user can refresh ([Claude](https://support.claude.com/en/articles/10593882-how-to-share-and-unshare-a-chat), [ChatGPT](https://help.openai.com/en/articles/7925741)) | Approval queue instead of prompt capture |

## Build instructions

These instructions are for the agent continuing the [agent planning system repo](https://github.com/RandyHaylor/agent-work-planning-system). Build this system by running its own process on itself, one level at a time, with the user approving every addition.

### Ground rules

1. Follow the Philosophy doc. Until the system can store quotes itself, use its honor-system checklist: the agent does the research, includes links, and records the user's requirements as closely to their words as it can. Treat this plan as the approved requirements.
2. Work on `main`. Branches start only when agents split off to work on separate modules.
3. Nothing enters this plan or the repo's plan docs without the user's explicit approval. Send proposals to the user as a list.
4. The process is the deliverable. A working result reached without the levels counts as a failure.
5. Never stop at the first problem. Finish what's possible at the current level, carry the issues up to the level that has to address them, then work back down.
6. Don't guess. If something isn't in this plan or the Philosophy doc, ask the user.
7. Leave the source repos untouched: [source-of-truth-agent-tool](https://github.com/RandyHaylor/source-of-truth-agent-tool), [ai-agent-fastReader](https://github.com/RandyHaylor/ai-agent-fastReader) and [quick-json-reader](https://github.com/RandyHaylor/quick-json-reader). Copy in and adapt what's needed.

### Starting point

The repo today, from its README:

- A Postgres-backed tree of workorders, task nodes and attached docs, served over HTTPS.
- Role-scoped bearer tokens enforced server-side, for admin, planner and worker.
- Multiple knowledge bases, a live export to disk, encrypted backups, and integration tests over real HTTPS against real Postgres.
- Python with FastAPI and psycopg; Postgres 16 via docker compose.
- `agent-planning-system.md`, `WORKFLOWS.md`, `PLAN.md`, `DEV_PLAN.md`, `skill/SKILL.md` and `agent_instruction_injections.json` hold the current process and rules.

Keep what works. Its roles, permissions, knowledge bases, visibility rules, version history and cascading revocation all carry over, as described in Roles and permissions above.

### Capabilities to bring in

Each of these comes from a section of this plan. How they become modules is decided at level 3, with the user's approval.

- **One tree, one generic node type,** with branches and purpose labels (Node tree).
- **Context summaries** that add up from the top node to a work node into a pre-prompt (Context tree).
- **User quotes:** local transcript capture, continuous context ranges, push-when-referenced, the special key, and the quote lifecycle including supersession (Quotes).
- **Document cache and reading:** the service fetches, caches and logs every source, and agents read it through a fastReader-style interface and cite by document ID and line. This is adapted from fastReader and quick-json-reader (Quotes).
- **Approval queue** on the wiki website (Approval queue).
- **Wiki website** where the user views the whole tree and adds addendums (Node tree).
- **Review queue and reviewer clients,** with async review of nodes, adapted from SoT's title and node review (Review).
- **Building and verification tasks,** with token-enforced limits and escalation (Building and verifying modules).
- **HTTPS interface plus a CLI adapter** with the exact same interface (Interfaces and harnesses).
- **Local harness client** with adapters for Claude, Codex, Pi and later harnesses (Interfaces and harnesses).
- **Task assignment and isolation guidance** (Task assignment and isolation).

### Level by level

The levels are recorded in `process-levels.md`.

1. **What we're doing.** Who needs what for it to work, and generally how. Load the Philosophy doc, this plan and the existing repo docs.
2. **Definition of done.** For the whole system, with its hard requirements and constraints, built from this plan's decisions. Anything new or unclear goes to the user as a proposal.
3. **High-level plan.** The whiteboard plan covering every capability above, with each piece's definition of done and requirements, approved by the user. Decide the repo layout here, with the user.
4. **Walkthroughs.** One node for the whole system. Walk through each scenario step by step, end to end, and carry any gaps back up:
   - A local Claude CLI session where the agent proposes in conversation and cites the user's "yes".
   - Fetching a document through the service and citing it by ID and line.
   - A web agent submitting proposals to the approval queue, and the user approving one with a note.
   - A node rejected in async review, then fixed and resubmitted.
   - A worker that can't meet its spec: it finishes what it can, escalates, turns in its work, and the node pauses.
   - A quote superseded, raising a discrepancy task for the user.
   - A deep module failing outside verification and escalating as a user review event.
5. **Module specs.** Propose the modules, which need not match the level 3 pieces. Each has clear documentation, an interface, types, a definition of done and tests, and is its own package only when that makes sense. External integrations get generic strategy-style wrappers.
6. **Test scaffold.** Build hollow modules and integration tests that pass against mocks, before any real development.
7. **Build.** Create task nodes, mint scoped worker tokens, and assign them. Workers build to pass the tests; outside agents verify against the original tests.

### Points to raise with the user

The existing repo and this plan differ in these places. Raise each one at the level where it comes up; none is decided here.

- The depth trigger flags level 4 and rejects level 5 under `plans`. This plan limits depth only when breaking a module's task into smaller tasks.
- The repo has fixed doc roles attached to nodes. This plan has one generic node type with purpose labels.
- The repo has a `summary` doc per node and ancestor `environment` docs. This plan has context summaries that add up from the top down.
- The README says the server "does not gate process steps such as `done` on reports or reviews". This plan adds a review queue and verification tasks.
- The README says "Mocks exist only under an `approval` doc". This plan builds mocked integration tests before development.
- Admin today is a browser login approved each session. This plan adds a wiki website where the user approves proposals and adds addendums.

## Open questions backlog

Empty for now. Questions are proposed to the user first, and only approved ones are added here, to be answered together in one batch.

## Spike backlog

Spikes run as tasks at whichever layer needs the answer.

- [ ] Claude desktop app: do `UserPromptSubmit` hooks run, and can output be injected?
- [ ] Codex desktop app: hook behavior, compared with the CLI
- [ ] Web chat connecting through the HTTPS interface

## Sources

- [source-of-truth-agent-tool](https://github.com/RandyHaylor/source-of-truth-agent-tool)
- [ai-agent-fastReader](https://github.com/RandyHaylor/ai-agent-fastReader)
- [agent-work-planning-system](https://github.com/RandyHaylor/agent-work-planning-system)
- [quick-json-reader](https://github.com/RandyHaylor/quick-json-reader) (linked from fastReader; not yet reviewed)
- [Codex hooks docs](https://learn.chatgpt.com/docs/hooks)
- [Claude Desktop on Linux (beta)](https://code.claude.com/docs/en/desktop-linux)
- [Claude help: share and unshare a chat](https://support.claude.com/en/articles/10593882-how-to-share-and-unshare-a-chat)
- [ChatGPT shared links FAQ](https://help.openai.com/en/articles/7925741)
