# Prototype Plan: Agent Planning Server
Started 2026-11-04. Companion to agent-planning-system.md. A dated decision log: later "Added" sections supersede earlier ones. The current state is summarized in DEV_PLAN.md and README.md.

> SUPERSEDED: the sections from here to "Stack" describe the 2026-11-04 prototype with owner-based permissions, `can_spawn`, and no nesting limit. Replaced by "two roles replace owner-based permissions", "depth limit", and later sections below. Kept for history.

## Decided in discussion (2026-11-04)
- One base node type. Plain container. No kinds.
- Every node has exactly one summary doc, created with the node.
- Owning a node = you planned it and delegate its work. You never do the work of a node you own.
- Owner writes the summary. Delegates write beneath.

## Node (base)
- id, parent_id, title, owner (token id), state, created_at
- state: open | blocked | done. Owner sets it. Parent may also set it.
- Everything else is an attachment (doc) or a child node.

## Doc (attachment)
- id, node_id, role, body (markdown), author (token id), created_at, updated_at
- role: summary | instruction | report | escalation | question | kb_proposal
- summary: one per node, written by owner
- instruction: written by owner, read-only to the assignee
- report: written by the assignee (what it built, what it proved)
- escalation: assignee asks; parent answers via `answer` field; `resolved` flag
- question: logged by parent for the audit trail
- kb_proposal: proposed KB change, handed off to the user

## Tree
- Single tree, one root. Two fixed children at bootstrap: `kb` and `plans`.
- No nesting limit.

## Token (auth)
- Bearer token. Stored hashed.
- Fields: id, label, scope_node_id, parent_token_id, can_spawn, revoked
- Root token created at bootstrap, scope = root, can_spawn = true. That is the user.

## Permissions (enforced server-side on every request)
- Read: scope node, every ancestor, every descendant. Nothing else.
- `kb` subtree: readable by all tokens. Writable by root token only.
- Create child node: anywhere in own scope subtree.
- Summary / instruction docs: writable only by the node's owner.
- Report / escalation / kb_proposal docs: writable by the scope-holder on its scope node or below.
- Edit a doc: author only. Summary and instruction on your own scope node: never.
- Mint child token: only if can_spawn. Child scope must be inside own scope. Child can_spawn ≤ own.
- Revoke: only tokens you minted.

## HTTPS API (small, flat, JSON)
- `GET  /me`                        → token label, scope node, can_spawn
- `GET  /nodes/{id}`                → node + its docs
- `GET  /nodes/{id}/tree`           → node with nested children (no docs bodies, titles + state only)
- `POST /nodes`                     → {parent_id, title, summary} → new node, owner = caller
- `PATCH /nodes/{id}`               → {state}
- `POST /nodes/{id}/docs`           → {role, body}
- `PATCH /docs/{id}`                → {body} | {answer, resolved}
- `GET  /escalations`               → unresolved escalations in my scope
- `POST /tokens`                    → {label, scope_node_id, can_spawn} → plaintext token once
- `DELETE /tokens/{id}`             → revoke
- Errors: 401 bad token, 403 outside scope, 404 unknown

## Stack
- Python 3, FastAPI, psycopg, uvicorn
- Postgres in docker compose
- TLS: uvicorn with a self-signed cert generated at first run; cert path configurable
- Port 8787 (8000 and 8443 are in use on this machine)
- `bootstrap` command: creates schema, root, kb, plans, prints root token once

## Skill file
- `skill/SKILL.md`: how an agent uses the endpoint with curl. Start from `/me`, read your scope node, read instruction, write report, escalate.

## Definition of done (prototype)
- Compose up + bootstrap works from clean state.
- Integration tests run over real HTTPS against the real Postgres: every endpoint, every permission rule above, including denials.
- No mocks.
- README: run, bootstrap, mint a dev token, example session.

## Out of scope for this prototype
- Viewer UI
- Notifications / push to agents (agents poll `/escalations`)
- Standing-rules review step
- Versioned doc history

## Added 2026-11-05: depth limit (enforced in the database)
- A project = a direct child of `plans`. Project is level 1.
- Level 4: allowed, but node is created with `needs_review = true`; response carries a warning. Triggers review with the user.
- Level 5: refused by a DB trigger. API returns 409 with message: open a separate project under `plans` for that branch, with its own plan and the same procedure.
- `kb` subtree and the fixed roots are exempt.
- Tests: level 4 flags, level 5 refused at the DB level even when bypassing the API.

## Added 2026-11-05: tech spikes
- New doc role: `spike`. Attachable to any node.
- Convention (in SKILL.md, not enforced):
  - Spikes that inform architectural decisions attach at the project's top-level node and are coordinated with the user.
  - Before building a large chunk on any platform, a small spike proving the platform is required. Example: a spinning 3D hello-world text running in three.js on the planned stack.
  - Proof is demonstrated: screenshots attached or referenced in the spike doc. Where the AI cannot honestly validate the result (video, motion, feel), the spike asks for human validation and says so.
- Write rule: same as `report`.

## Added 2026-11-05: escalation path (clarified)
- A worker escalates to its parent, the owner of its node.
- Planner and dev manager escalate to the user, because the user owns their nodes.
- Server rule stands: the node owner, or root, answers an escalation.

## Added 2026-11-05: hollow before full
"If we can't solve the big picture first, how can we hope to build the details?"
- Every node is built hollow before it is built full.
- Hollow means: exists, reachable from its parent, testable from the outside, returns a placeholder.
  - Module: folder, types, init, stub that returns something.
  - Document: empty sections, each named.
  - Any design: its named parts.
- A section whose content is unknown still exists. Its body says what must be researched to fill it.
- The skeleton has tests, written first, that pass against the stubs. Hollow = those tests are green.
  - Those tests are the rails for every dev agent beneath. Dev agents may add tests, never redefine these.
- Not every question is answered up front. Placeholders, interfaces, types, and contracts are.
- The whole skeleton is built and proven before any work is delegated beneath it.
- Filling is the delegated work. Delegates fill; they never add bones.
- A missing bone found later is a structural change. Escalates to the top, with the user.
- Precedent: walking skeleton (Cockburn), tracer bullet (Pragmatic Programmer), TDD stubs, state machines mapped before bodies.
- Hollow is NOT a node state and NOT a server gate. It is the starting condition of every node.
  - A node isn't a node until it has its basic scaffolding: interfaces, types, placeholders.
  - The planning phase that defines the nodes creates them already hollow.
  - The dev agent spawned for a node is told to finish it.

## Added 2026-11-05: where TDD applies
- Real TDD at the interface and module level. These tests are the skeleton's rails, written before delegation.
- Micro TDD inside a module is at the dev agent's discretion, basic and where it makes sense.
  - Reason: agents are not good or efficient at the micro TDD humans describe, because few humans do it well and no agent is trained on it done right.
- Integration tests stay fully real, per the standing rules.

## Added 2026-11-05: packaging as a skill
- The system ships as a skill usable by any agent harness. Not tied to Claude.
- The planning agent, following the skill:
  - Stands up the server (compose, bootstrap) or connects to a running one.
  - Plans the project with the user.
  - Builds and proves the hollow skeleton.
  - Mints scoped tokens and hands them to dev agents with the skill file.
  - Answers escalations; escalates to the user.

## Added 2026-11-05: hollow is proposed per project
- The planning agent proposes the hollow for each project. The user approves it.
- With the user, it sorts requirements into three bands:
  - Firm up front: interfaces, types, contracts, modules, names. Built into the skeleton.
  - Design notes: less consequential details, recorded but not binding.
  - Dev agent discretion: decided inside the module, within the parameters above.
- Only the firm band is part of hollow.

## Added 2026-11-05: shared stack visibility
- Dev agents must see the project's tech stack, dependencies, and shared assets.
  - Reason: reuse shared assets instead of bringing in parallel tools. Not three math packages and four UI approaches.
- Where it lives: an `instruction` doc on the project's top node, written by the planner.
  - Every descendant can read it under the existing rule (ancestors are readable).
  - No schema change needed.
- Rule for dev agents: check the project stack before adding any dependency. A new dependency is an escalation.

## Added 2026-11-05: planner must specify formatting
- Found in the first live test: the planner asserted exact table text in tests without ever stating how header cells are padded. Tests disagreed; a dev agent guessed.
- Rule: the planning agent must specify formatting for everything that has a form.
  - Responses and outputs of the thing being built: whitespace, alignment, line endings, trailing newline, header vs body, error message shape.
  - Work products: file layout, naming, commit shape.
  - Documentation: README sections, report structure.
  - Server entries: what a report, escalation, spike, question doc contains, in what order.
- A format the planner does not want to decide is declared dev discretion in the instruction, by name. Never silent.
- Goes into the skill file as a planner step before delegation.

## Added 2026-11-05: planning spikes before approval
- Planning has a sketch step before the formal plan: the planner sketches the solution and identifies what must be proven first.
  - Something in the existing repo: does it do this?
  - A new concept: does it work locally at all?
- Those proofs are tech spikes, done before the plan is approved and before any scaffold exists.
  - Throwaway code. Never the start of the real build.
  - Done in isolation, each in its own space.
- Structure: the project node gets a `planning spikes` child node (level 2). Each spike is a child beneath it (level 3), with its own instruction and a `spike` doc for the result.
- The planner may spawn agents for spikes, one per spike node, with scoped tokens, same as dev agents.
- Results feed the plan. The plan is not approved until every spike it depends on has reported.
- Only after approval: the formal scaffold, the hollow nodes, and delegation.
- If no spike is needed, the planner says so in the project summary and why.

## Added 2026-11-05: two roles replace owner-based permissions
- Found in both live tests: owner-based rules blocked the planner from logging questions on the project node, and planners fell back to the root token.
- Tokens carry a role. Permissions come from the role and the scope, not from node ownership.
- Planner / dev manager: full rights on every node in its scope. Reads and writes everything: summaries, instructions, questions, state, children, tokens.
- Dev worker: reads only its own node and what is beneath it. Writes reports, escalations, spikes, kb proposals on its node, and creates nodes beneath it. Nothing else.
- The user does not access the server directly. The user works through the planner.
- Root token exists only to bootstrap and mint the first planner token.
- Ownership stays as a record of who created a node, not as a permission source.

## Added 2026-11-05: the environment doc
- Dev workers do not see the project. They see one shared doc from above: the environment.
- New doc role `environment`, on the project node, written by the planner.
  - Contents: a generic project summary, tech stack, dependencies, shared assets, conventions.
  - Framing, stated in the doc itself: this is the larger environment you are working within. You are not building it.
- Read rule for dev workers: own node and beneath, plus every `environment` doc on an ancestor. No other ancestor docs: no summaries, instructions, questions, reports, escalations.
- The planner keeps the stack there, in one place, instead of copying it into every instruction.

## Added 2026-11-05: planner is never blocked by its workers
- Spawning a dev worker never blocks the planner. The planner stays live and polls `/escalations` throughout a run.
- The blocking seen in the two live tests was a harness artifact: the planner was itself a nested subagent. Not a system rule.
- Future tests run the planner as a top-level session.

## Added 2026-11-05: an escalation is a blocker
- A dev worker escalates only when it is blocked. By definition the worker stops and waits for the answer.
- No tiers of escalation. A question that does not block is not an escalation; the worker proceeds within its instruction and discretion and notes the call in its report.

## Added 2026-11-05: planning order, with the reference run required
1. Informal outline with the user.
2. Identify anything tricky or unique that needs proving. Spike only those. Not fishing for spikes; most projects need none.
3. Formal plan: work, DoD, interfaces, bands, modules, names, formatting. User approves.
4. Skeleton: hollow nodes, rails, acceptance tests with exact values.
5. Reference run, required: a throwaway implementation of the rules, outside the workspace, never delivered. Every acceptance test passes against it. Any failure is a wrong expected value or a missing rule; fix before commit.
6. Skeleton commit. The diff baseline.
7. Delegate.

## Added 2026-11-05: node closure
- DoD is defined by the planner and the user, in the plan.
- A worker never closes its node. When a worker stops, the planner sees it and checks the node's state against the DoD with real tests.
- Planner approves closure: node set done, and the planner starts the next dependent node(s).
- Or the planner re-engages the worker to continue, because the work does not meet the requirements.
- The same applies to the project node: the planner closes it when every node beneath meets its DoD.
- The standing-rules review is part of the planner's closure check. No separate review agent for now.

## Added 2026-11-05: proof before reliance, proof before done (standing rule)
- Nothing about a system is known to work the way we think until a real integration test or actual use proves it. No agent moves forward on that knowledge until it is proven.
- The same proof is required before work is called done. Unit tests passing means it is time to integration test.
- Added to the standing rules in agent-planning-system.md and to both halves of skill/SKILL.md. Worker reports must carry the real proof; planner closure checks it.

## Added 2026-11-05: what this tool is, at this stage
- A local tool, run on a developer's machine alongside an AI agent harness that can run multiple agents.
- Not an internet service. Not a security product.
- Tokens are lane-keeping, not security. They exist so that dev agents can only see and write their own node. Nobody is defending against a hostile agent or a network attacker.
  - So: self-signed cert and `curl -k` are fine. No cert pinning. No threat model beyond "keep agents in their lane".
  - Revocation still matters for lane-keeping: a finished worker should lose its lane. Cascading revocation is wanted for that reason, not for security.

## Added 2026-11-05: backup to disk on every write
- The database is the working store. The record of a project must also exist on disk.
- After every write that touches a project (node create, state change, doc create, doc edit, escalation answer), the server writes that project's full subtree to disk.
- Layout: `PLANNER_BACKUP_DIR/<project-id>-<slug>/`
  - `tree.json`: nodes with ids, parents, titles, states, flags.
  - `docs/<node-id>-<role>-<doc-id>.md`: one file per doc, body verbatim, header with author, timestamps, answer and resolved where present.
- `kb` is backed up the same way as its own folder.
- Default dir: `backups/` under the repo, gitignored. Configurable.
- Synchronous, in the request. A failed backup fails the write.

## Added 2026-11-05: gaps against the initial design notes, closed
- Survey step for existing systems: kb and user first, targeted checks, proof by real test committed at the matching layer, recorded as a `survey` doc. Deep dive only with permission, offered as a `kb_proposal`.
- Formal plan adds flow and user story, and on existing systems: what changes, what is added, what is improved first.
- The user approves the plan as written on the server, not only in chat.
- `approval` doc: the record of any mock or partial test, planner-written after user approval. No approval doc, no mock.
- Roadblock stops everything: node `blocked`, dependents not started, user decides.
- Knowledge base apply path: planner applies a `kb_proposal` only after the user approves; `kb` is writable by planners.
- Closure review records a standing-rules pass as a `review` doc: naming, generic modules, isolation, approvals.
- "The user" is whoever called the planner.
- Closed: the old "append vs beneath" question. Docs on the node and children beneath it.

## Added 2026-11-05: clarifications after the second blind review
- The planner is the admin. It reads and writes everything in `plans` and `kb`. Planners are never blind to sibling projects or the larger environment. Any test or rule implying otherwise is wrong and is removed.
- Backup is one at a time per project. A write that arrives while a backup is running waits its turn. Implemented as a per-project database lock held for the write and its backup.
- Bootstrap is all-or-nothing.
- Token listing shows whether a token actually works, including tokens dead because a parent was revoked.
- Workers cannot edit the docs that define their task. That is the design. Workers write their own docs on their node and beneath it, and may edit docs they authored, including the summary of a sub-node they created. The planner reviews those notes at closure and folds them into the final work docs or the kb as approved.
- No default database password. Bootstrap generates one into a gitignored local env file that compose and the server read. Server and database bind to localhost only.

## Added 2026-11-09: after the third blind review
- Doc version history: every edit to a doc keeps the previous version. Append-only, written by the database on update. Readable by planners. This is the audit trail.
- Unchanged: a worker never edits the planner's docs on its assigned node. Only the planner or dev manager updates a task node's summary, instruction, environment, approval, or review.
- Nodes are immutable for now: no delete, rename, or reparent. A mis-created node is set `blocked` with a note. Revisit if it hurts.
- Fixes: creating a project backs it up at once; kb proposals can be resolved with an answer and listed; `needs_review` can be cleared and listed; backup writes go to a temp dir then rename; clear error on an unbootstrapped database.
- Docs: "no nesting limits" and "reachable over the internet" removed from requirements; superseded permission sections in this file marked as such; dates corrected to local dates; the skill names pytest as the assumed runner.

## Added 2026-11-09: multiple projects, multiple kbs, three roles
- Everything decided before this section was in the context of a single project. This section is the multi-project layer.
- Roles:
  - `admin`: top-level. Not a project planner. Maintains the knowledge bases through conversation with the user, creates projects, assigns kbs to projects, controls project visibility. One per server, minted at bootstrap (replaces the root token).
  - `planner`: scoped to one project. Full read and write inside it. Read-only on every other visible project. Cannot edit any kb.
  - `worker`: unchanged. Its node and beneath, the project's assigned kbs, ancestor environment docs.
- Projects:
  - Each project has a uuid, assigned at creation, used in the API and the backup directory.
  - `POST /projects` (admin) creates the node under `plans`, the uuid, and mints the project's planner token. Returns uuid and token once.
  - `visible` flag, default true. A hidden project is readable only by its own planner, the admin, and projects granted explicit visibility.
  - Admin grants a project read access to a hidden project: `POST /projects/{uuid}/visibility {viewer: <uuid>}`.
- Knowledge bases:
  - Multiple kbs, each a child of `kb`, each with its own uuid. Product, company, context, whatever is needed.
  - Admin assigns any number of kbs to a project. Planner and workers of that project read only the assigned kbs.
  - Agents never edit a kb. They write `kb_proposal` docs. The admin applies changes after a conversation with the user. (Supersedes "kb writable by planners".)

## Added 2026-11-09: admin is a user-approved session
- The top-level admin role is something the user approves, every time.
- Admin password: set by the user at bootstrap, typed interactively, never printed, stored as a hash in the database. Only the user knows it. Changeable with the same interactive command.
- Bootstrap no longer prints a persistent admin token. There is none.
- Admin login: the agent runs `uv run ai-project-planning-server admin-login`. The command opens a browser window to the local server's login page. The user types the password directly into that page; the agent never sees it. On success the server creates an admin session token held in memory only, the command receives it and prints it once, and the agent uses it like any other token.
- Admin sessions do not survive a server restart. They can also be ended with `uv run ai-project-planning-server admin-logout` or expire after a configurable idle time (default 8 hours).
- Who does what, written for agents:
  - User: approves plans, approves kb changes, approves admin sessions, resolves roadblocks.
  - Admin agent (session): creates kbs and projects, assigns kbs, sets visibility, applies approved kb changes, hands the project's planner token to the planner.
  - Planner agent: one project, start to finish, per the planner half of the skill.
  - Worker agent: one node, per the worker half.

## Added 2026-11-09: agent isolation is the user's job, not this app's
- Whether agents run in their own VMs, containers, or one shared machine is decided by the user and the project. It stays out of this app's scope.
- The instructions given to agents stress: the only valid information about a project is what the server holds (the document tree), plus any reference the planner explicitly grants, in the form it is given. Example, in a local session without guard rails: "look at this folder for reference, but do not edit it."
- If a project requires agents to work in isolation, the project's environment doc says so, and the planner is responsible for making it happen.

## Added 2026-11-09: never make up details or rules (standing rule)
- Agents infer and guess far too much. An agent must never add a detail, limit, number, or rule the user did not state.
- Example that prompted it: the user said "good clear naming that describes what something does"; the agent wrote "keep it to one line". That was an arbitrary, harmful inference.
- Gaps are named as the agent's own assumption and asked about, or left open. Never quietly turned into a rule.
- Added to the standing rules in agent-planning-system.md and to both halves of skill/SKILL.md.
- Naming guidance in this system stays as stated: use good clear naming that describes what something does. No explicit naming rules in the generic system; those belong to a company or product knowledge base or a project spec.

## Added 2026-11-09: the deadbolt standard
- Tokens, the admin login window, and the database password keep honest agents honest. That is the whole aim, like a deadbolt on a house door.
- An agent that reads the env file or the backups folder, or opens the admin login window, is stepping out of its lane. The rules tell it not to. Nothing in this app tries to stop a determined one; that is the user's job through isolation, if they want it.
- Admin login is rare. The user knows which agent asked by timing. No label on the window.
- The rule that the server is the only source of project truth is now an injected session-start rule for every agent type.

## Added 2026-11-09: starting a project needs no admin
- Any agent with access to the server creates a project: `POST /projects`. The response carries that project's planner token. The agent is now the project's planner. Not hidden by default.
- Server access token: a file at the server location, generated by bootstrap, required on every request in addition to the role token. Nothing without local disk access reaches the server.
- The planner decides which kbs its project sees. Planners read every kb in order to choose. `PATCH /projects/{uuid} {kbs}` is the planner's call for its own project. A task node may override the kb set for the agents beneath it.
- Admin remains for: writing kbs, hiding projects, granting visibility into hidden projects, applying kb proposals.
- Admin escalation, harness agnostic: the planner either spawns a new unattached agent to become admin (the user types the password), or instructs the user to start an admin session and passes on what needs doing.

## Added 2026-11-09: where tokens live, and sessions per task
- A token exists in the agent's session and nowhere else on the agent side. The app does not save it for the agent.
- Agent harnesses strongly try to train against agents looking into other agents' session files. We officially lean on that.
- An admin session can retrieve or change the token of any agent at any level. A planner can retrieve or change the token of any dev agent in its project.
  - The server stores only hashes, so retrieve and change are one operation: rotate. A new plaintext is issued once; the old one stops working.
- One agent session may hold several task tokens and work several tasks. Encouraged when the tasks are very small, because new sessions are expensive on almost every harness.
- Large or complex tasks go to separate agents, or to agents forked from another session.
- The planner suggests the split at its discretion, and invites the user to approve or alter it before deploying.
- Correction, same day: retrieve means retrieve. The server keeps the plaintext in a table readable only through `GET /tokens/{id}/secret`: admin for any token, a planner for the worker tokens in its project and its own. Nothing is forced to change; rotation exists only as the "change" half, used when wanted. A deadbolt, not a vault door.

## Added 2026-11-09: planner is the project admin, full stop
- A planner token is always scoped to a project node. The server refuses any other scope for a planner.
- Two planners on one project are two project admins. Either may edit the other's docs, rotate or retrieve the other's workers' tokens, and clear the level-4 flag. By design.
- Reviews that flag planner powers inside its project as defects are measuring against a model this system does not use.
- The admin login handler runs off the event loop so other requests do not wait on password hashing.
- One local file holds what anyone with disk access needs to reach the server: the database password and the server access token, owner-only permissions.
- Test runner: a per-run compose project name and log path, so runs never collide.

## Added 2026-11-09: backup is a full encrypted database backup
- A backup is a full dump of the database, encrypted. Restore replaces the database from a chosen backup.
- Encryption: at bootstrap the server creates a keypair. The public key is stored in the clear; the private key is stored encrypted with the admin password. Backups are encrypted to the public key, so no password is needed when a task completes. Restore asks for the admin password to unlock the private key.
- Trigger: a new backup every time a task node is set done.
- Retention: one per day (the oldest that day), one per task for the last 10 tasks, one per week, one per month.
- Disk space is not a concern. Code does not live in the database.
- A backup is a backup: whatever was in the database is in it, including anything later rolled back. That is the point. Note, not a procedure: after a rollback for a severe security reason, stop work, take a new backup, then load and fix or purge older backups in turn.
- The per-write markdown mirror stays and is called what it is: a live export, not the backup.
- Nodes are editable by the project's planner or the global admin: title, parent (within the project, depth rule enforced on the move too), and delete. Supersedes "nodes are immutable for now".
- A project planner can hand off the project planner role to a new agent when needed, and is permitted to pass the planner token to that agent with the permission of the user.
- Retention clarified: backups are backups, not part of regular use. On-demand backups are wanted. Any backup that is not the week or month backup counts toward the 10 latest, whatever triggered it. No special case for the newest file.

## Added 2026-11-09: "project" becomes "workorder"
- Found in use: an agent read "project" as a whole app, because nothing stated a size. The docs failed.
- The unit of work this system plans and runs is a workorder. Neutral term: it fits a feature, a sprint's worth of work, a larger tech spike, a broad research phase, a fix.
- A workorder is never used to fully encapsulate a large project, app, product, or long-term task. Those are defined in the product or company kb, by the admin agent.
- Updates to the kb come from planning or dev agents creating external documents (kb proposals) submitted to an admin agent, who updates the central kbs.
- Rename everywhere: `projects` → `workorders` in the API, schema names, backups, docs, and skill. Nodes inside stay tasks. The planner runs one workorder.
