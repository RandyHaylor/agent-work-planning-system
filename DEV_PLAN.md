# Dev Plan

As of 2026-11-05. The prototype is built and green. This doc holds what is decided, what the prototype does, the judgment calls awaiting review, and what is still open. Design detail lives in `PLAN.md`; process and rules in `agent-planning-system.md`.


## Decided - the shape of the system

One base node type, no kinds
- Plain container: title, owner, state, parent
- One summary doc per node, written by the owner
- Everything else attaches as a doc with a role

Owning a node means delegating its work
- The owner never does the work of a node it owns
- Delegates write beneath

Single tree
- Fixed roots `kb` and `plans`
- A project is a direct child of `plans`

Token scope is a subtree
- Read: node, ancestors, descendants
- Write: beneath only
- Own instruction and summary never writable by the holder

Depth limit enforced in the database
- Level 4 flagged `needs_review`
- Level 5 refused; branch becomes its own project

Tech spikes are docs
- Role `spike`
- Architectural spikes at project top, coordinated with the user
- Hello-world proof required before building large on a platform


## Built - prototype, 33 tests green from a clean state

Server
- FastAPI, psycopg, uvicorn
- Postgres 16 in docker compose, port 5433
- HTTPS 8787, self-signed cert generated at first run
- Isolated permissions module with its own unit tests

Ten endpoints, flat JSON
- Nodes, docs, tokens, escalations, me

Skill file for agents
- `skill/SKILL.md`, curl-based

Tests
- Real HTTPS against real Postgres
- Every endpoint, every rule, every denial
- Depth trigger proven by direct SQL insert


## Awaiting user review - builder judgment calls

Escalation answers restricted to node owner or root
- PLAN said "parent"; owner is the parent in practice

`question` docs are owner-only
- PLAN did not list a write rule

`kb_proposal` is written in the agent's own scope node
- `kb` subtree is root-only


## Open - left to plan, decide, or discuss

Who deploys dev agents
- Planning agent, or a dedicated dev manager agent

Where escalations surface to the user
- Currently polled via `GET /escalations`
- No push, no notification

How a knowledge base proposal is applied
- Hand-off exists as a doc; the apply step does not

How permission is granted for sub-agent spawning
- `can_spawn` on the token today
- Delegated internal design calls not represented

How mock or partial test approvals are recorded

Who performs the standing-rules review step

Where proven understanding from the survey is recorded

A name for the real-world tests
- If "integration test" is not strong enough

Node content format
- Markdown body today; JSON structure not revisited


## Next - in order

1. User reviews the three judgment calls above
2. Viewer: slide-like read-only rendering of a node and its subtree
3. Standing-rules review step, and who runs it
4. Doc version history
5. Push or notify on escalation


## Out of scope for the prototype

- Viewer UI
- Notifications to agents
- Standing-rules review step
- Versioned doc history
