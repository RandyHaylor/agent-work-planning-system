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


## Decided 2026-11-05 - scope at this stage

A local tool on a developer's machine
- Runs beside an agent harness that spawns multiple agents
- Not an internet service, not a security product

Tokens are lane-keeping, not security
- They keep a dev agent inside its node
- Self-signed cert and `curl -k` are fine; no cert pinning
- Cascading revocation is wanted so a finished worker loses its lane

Every write is mirrored to disk per project
- `backups/<project>/tree.json` plus one markdown file per doc
- Synchronous; a failed backup fails the write


## Second blind review 2026-11-05

Fixed
- Backup serialized per project; bootstrap all-or-nothing
- Token listing shows effective liveness
- Workers edit docs they authored
- No default database password; server and database on localhost only
- Dead code, cycle guard, lockfile committed
- Skill and process doc contradictions on kb and open items

Rejected as not a defect
- Planner reading sibling projects: planners are admins by design
- Planner revoking in its own chain: admin

Design concerns carried forward
- Validated only on small deterministic CLIs; next test needs a UI or external service
- Server enforces lanes only; process steps are not server-gated by design


## Cold review 2026-11-05 - what it found and what we did

Fixed now
- Revocation did not cascade; no token listing
- Test runner wiped the live database; now an isolated compose project
- Node creation was not transactional

Clarified, not changed
- TLS is `curl -k`: acceptable for a local lane-keeping tool
- Depth trigger is insert-only; nothing reparents today

Still open
- `needs_review` cannot be cleared or listed
- Planners can edit worker reports in place; no doc history
- `PLAN.md` carries superseded sections; "no nesting limits" contradicts the depth rule
- Sibling interfaces travel only by the planner copying them into instructions
- Nothing checks the server plan matches what the user approved in chat


## Decided - two roles, not ownership

Tokens carry a role
- Permissions come from role and scope, never from who created a node

Planner / dev manager
- Full read and write on every node in its scope
- Mints and revokes tokens beneath it
- The user works through the planner and never touches the server

Dev worker
- Reads only its own node and beneath, `kb`, and every `environment` doc above it
- Writes reports, escalations, spikes, kb proposals; creates children; edits docs it authored
- Cannot edit the planner's docs, cannot see ancestors, cannot set state, cannot mint

The planner is the admin
- Sees every project and the whole environment
- Never blind to siblings by design

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

Three live tests, scored on dev worker deviations
- csvmd, Opus planner, five modules: zero deviations; one spec hole filled by a worker instead of escalated
- linedupe, Opus planner, three modules: zero deviations; planner caught its own wrong expected value in the reference run
- wordfreq, Fable planner on the two-role server, two modules: zero deviations, zero escalations


## Decided 2026-11-09 - admin is a user-approved session

No standing admin token
- The user sets the admin password at bootstrap; hashed in the database; only the user knows it
- An agent runs `admin-login`, which opens a browser window; the user types the password there
- The server issues an in-memory session token; the agent never sees the password
- Sessions end on logout, idle expiry, or server restart

Who does what is written in WORKFLOWS.md
- User approves; admin maintains kbs and creates projects; planner runs one project; worker finishes one node


## Decided 2026-11-09 - multiple projects, multiple kbs, three roles

Everything decided earlier was in the context of one project

Admin
- Top-level; not a project planner
- Maintains kbs through conversation with the user; the only kb writer
- Creates projects, assigns kbs, controls visibility
- Minted at bootstrap; replaces the root token

Planner, one per project
- Full write in its project; read-only on other visible projects
- Reads only the kbs assigned to its project; never writes a kb
- Mints workers only

Projects and kbs have uuids
- `POST /projects` creates the project and mints its planner token in one call
- Several kbs may exist; any number assigned to a project
- Projects visible to all planners by default; a hidden project needs an explicit grant from the admin


## Decided 2026-11-09 - after the third blind review

Doc version history is the audit trail
- Every edit keeps the previous version, append-only, written by the database
- Readable by planners; a worker reads only its own docs' history
- Included in the per-project backup

Workers still never edit the planner's docs on their assigned node
- Only the planner or dev manager updates a task node's summary, instruction, environment, approval, review

Nodes are immutable for now
- No delete, rename, or reparent; a mis-created node is set `blocked` with a note

Fixed
- Creating a project backs it up at once
- kb proposals can be resolved and listed; `needs_review` can be cleared and listed
- Backup writes are atomic: temp dir then rename
- Clear error on an unbootstrapped database


## Open - left to plan, decide, or discuss

Who or what notifies the planner that a worker stopped
- In a harness, the spawn completion; on the server, nothing yet

Marker design
- Deletion should leave clean code: no orphan import

Packaging as an installable skill
- Today the skill is a file in the repo; nothing registers it with a harness

Process validated only on small deterministic CLIs
- Three runs, eight workers, zero worker deviations
- Exact-value acceptance tests and a reference run will not fit UI, GPU, or network work as-is


## Next - in order

1. A live test on something with a UI or an external service, planner as a top-level session
2. Viewer: slide-like read-only rendering of a node and its subtree
3. Skill packaging for a harness
