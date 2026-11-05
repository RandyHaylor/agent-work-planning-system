# Dev Plan

As of 2026-11-05, after two live tests with Opus planners. This doc holds what is decided, what is built, and what is open. Design detail lives in `PLAN.md`; process and rules in `agent-planning-system.md`.


## Decided - the shape of the system

One base node type, no kinds
- Plain container: title, owner, state, parent
- One summary doc per node, written by the planner
- Everything else attaches as a doc with a role

A node isn't a node until it has its scaffolding
- Planning creates nodes already hollow
- Hollow is the starting condition, not a state and not a gate

Owning a node means delegating its work
- The owner never does the work of a node it owns

Single tree
- Fixed roots `kb` and `plans`
- A project is a direct child of `plans`

Depth limit enforced in the database
- Level 4 flagged `needs_review`
- Level 5 refused; the branch becomes its own project


## Decided - two roles, not ownership

Tokens carry a role
- Permissions come from role and scope, never from who created a node

Planner / dev manager
- Full read and write on every node in its scope
- Mints and revokes tokens beneath it
- The user works through the planner and never touches the server

Dev worker
- Reads only its own node and beneath, plus every `environment` doc above it
- Writes reports, escalations, spikes, kb proposals; creates children
- Cannot see ancestors, cannot set state, cannot mint

The environment doc
- One shared doc on the project node: generic summary, stack, dependencies, shared assets
- Framed as the environment workers are within, not building
- The only thing from above a worker can see

Root token
- Bootstrap and the first planner token only


## Decided - how planning runs

Seven steps, in order
1. Informal outline with the user, one thread at a time
2. Spikes only for what is tricky or unique; not fishing for them
3. Formal plan: work, DoD, interfaces, three bands, modules, names, formatting, delegation order
4. Plan written to the server: project node, environment doc, one node per module
5. Skeleton: hollow nodes, rails green on stubs, acceptance tests under strict expected-fail
6. Reference run, required: a throwaway implementation proves every acceptance value before commit
7. Skeleton commit is the diff baseline; then delegate

The three bands
- Firm up front: interfaces, types, contracts, modules, names
- Design notes: recorded, not binding
- Dev discretion: named item by item, never silent

Planner specifies formatting for everything with a form
- Outputs, errors, work products, documents, server entries
- Found in test one: exact table text asserted with no header padding rule

TDD at the interface and module level
- Rails and acceptance tests are the rails
- Micro TDD inside a module is dev discretion


## Decided - how work runs

An escalation is a blocker
- The worker posts it and stops; it never picks
- A non-blocking question is a discretion call, recorded in the report

Escalation path
- Worker to planner; planner to user
- No agent changes scope, interfaces, or the plan

Planner is never blocked by its workers
- Stays live, polls escalations throughout
- Blocking seen in tests was a nested-subagent artifact

Node closure
- DoD defined by planner and user
- Worker stops; planner checks against DoD with real tests
- Planner closes and starts the next dependent node, or re-engages the worker
- Standing-rules review is part of that check


## Built - prototype, green from a clean state

Server
- FastAPI, psycopg, uvicorn; Postgres 16 in compose on 5433; HTTPS 8787
- Isolated permissions module with its own unit tests
- Ten endpoints, flat JSON; skill file for agents

Two live tests with Opus planners, scored on dev worker deviations
- csvmd, five modules: zero deviations; one spec hole filled by a worker instead of escalated
- linedupe, three modules: zero deviations; planner caught its own wrong expected value in the reference run


## Open - left to plan, decide, or discuss

Who or what notifies the planner that a worker stopped
- In a harness, the spawn completion; on the server, nothing yet

How a knowledge base proposal is applied
- Hand-off exists as a doc; the apply step does not

How mock or partial test approvals are recorded

Where proven understanding from a survey is recorded

Marker design
- Deletion should leave clean code: no orphan import

Packaging as an installable skill
- Today the skill is a file in the repo; nothing registers it with a harness


## Next - in order

1. Run a third test with the planner as a top-level session, not a nested agent
2. Viewer: slide-like read-only rendering of a node and its subtree
3. Doc version history
4. Skill packaging for a harness
