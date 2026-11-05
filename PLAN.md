# Prototype Plan: Agent Planning Server
As of 2026-11-04. Companion to agent-planning-system.md. Only the prototype's decisions.

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
