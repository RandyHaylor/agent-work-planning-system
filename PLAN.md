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
