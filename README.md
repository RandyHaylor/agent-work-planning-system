# Agent Planning Server

A process for humans and agents to plan work together, with a hosted server that enforces who may read and write what. The prototype runs today: Postgres, a small HTTPS API, 33 real tests, no mocks.


## The problem - agents drift, context leaks, tools don't hold

Agents drift on long projects
- Scope creep
- Invented interfaces
- "Close enough" tests

Context leaks
- Every agent sees everything
- Nobody owns anything

Existing tools fail one requirement each
- Shallow nesting
- Permissions don't hold
- Not fully open source


## The system - a process, not an AI product

Works for any mix of humans and agents
- Rules stand either way
- Not tied to Claude or any harness

The user writes requirements and interfaces, never code

Design happens up front, never on the fly
- Modules
- Interfaces
- Names

Nothing in existing code counts as understood
- Until a real test proves it


## The tree - one node type, infinite nesting

A node is a plain container
- Title, owner, state, parent
- One summary doc, always, written by the planner
- Not a node until it has its scaffolding: planning creates it hollow

Owning a node means delegating its work
- Never doing it

Everything else is an attached doc
- `instruction`, `environment`, `report`, `spike`
- `escalation`, `question`, `kb_proposal`

Single tree, two fixed roots
- `kb` - knowledge base
- `plans` - projects


## The permissions - two roles, the actual product

Each agent holds a bearer token with a role and a scope subtree

Planner: full rights on everything in scope
- Writes summaries, instructions, environment, questions, state
- Mints and revokes tokens beneath it
- The user works through the planner, never the server

Worker: its own node and beneath, nothing above
- Plus every `environment` doc above it: the stack it works within, not builds
- Writes reports, escalations, spikes, kb proposals; creates children
- Cannot set state, cannot mint, cannot see ancestors

Knowledge base: everyone reads, only root writes
- Agents propose changes as `kb_proposal` docs

Enforced server-side on every request
- A wall, not a convention


## The limits - four levels, then a new project

Project = direct child of `plans` = level 1

Level 4 is a warning
- Node created with `needs_review = true`
- Response carries a `warning`
- Triggers review with the user

Level 5 is refused by a Postgres trigger
- API returns 409
- Open a separate project under `plans` for that branch
- Same procedure, its own plan

`kb` and the fixed roots are exempt


## The spikes - prove the platform before building on it

Doc role `spike`, attachable to any node

Architectural spikes attach at the project's top node
- Coordinated with the user

A hello-world proof is required before building large
- Example: spinning 3D text in three.js on the planned stack

Proof is shown, not claimed
- Screenshots attached or referenced
- Human validation requested where the AI can't honestly judge
  - Video, motion, feel


## The planning order - prove the skeleton before delegating

1. Informal outline with the user, one thread at a time
2. Spikes only for what is tricky or unique
3. Formal plan: work, DoD, interfaces, three bands, names, formatting
4. Plan written to the server
5. Hollow skeleton: rails green on stubs, acceptance tests expected-fail
6. Reference run: a throwaway proves every expected value
7. Skeleton commit is the diff baseline; delegate


## Escalation - a blocker, and no agent changes the plan

Worker is blocked: it posts the escalation and stops
- Planner answers within scope, or escalates to the user
- A question that does not block is a discretion call, recorded in the report

Every question is logged
- Context for the next plan
- Audit trail

Can't build to spec? Stop
- Never substitute something else

Planner closes nodes
- Checks each stopped worker against the DoD with real tests
- Closes and starts the next, or re-engages


## Run it - compose, bootstrap, serve

```
docker compose up -d                 # Postgres on 5433
uv sync --extra test
uv run python -m server bootstrap    # prints ROOT_TOKEN once; keep it
uv run python -m server              # HTTPS on 8787, self-signed cert in certs/
```

Env: `PLANNER_DSN`, `PLANNER_PORT`, `PLANNER_HOST`, `PLANNER_CERT_DIR`

Reset: `docker compose down -v`, then bootstrap again


## Use it - mint a token, hand over the skill file

```
H="Authorization: Bearer $ROOT_TOKEN"
curl -sk https://localhost:8787/nodes/1/tree -H "$H"
curl -sk https://localhost:8787/nodes -H "$H" -H 'content-type: application/json' \
  -d '{"parent_id":3,"title":"plan A","summary":"..."}'
curl -sk https://localhost:8787/tokens -H "$H" -H 'content-type: application/json' \
  -d '{"label":"planner","role":"planner","scope_node_id":3}'
```

Give the agent the token plus `skill/SKILL.md`

A dev agent's session
```
GET  /me                          -> scope_node_id = 5
GET  /nodes/5                     -> summary + instruction (read-only)
POST /nodes/5/docs  {"role":"escalation","body":"..."}
GET  /nodes/5                     -> escalation answered, resolved
POST /nodes/5/docs  {"role":"report","body":"what was built and proven"}
```


## The API - ten endpoints, flat JSON

| Method | Path | Does |
|---|---|---|
| GET | `/me` | Token label, scope, can_spawn |
| GET | `/nodes/{id}` | Node + docs |
| GET | `/nodes/{id}/tree` | Nested titles + state |
| POST | `/nodes` | Create child, owner = caller |
| PATCH | `/nodes/{id}` | Set state |
| POST | `/nodes/{id}/docs` | Attach doc |
| PATCH | `/docs/{id}` | Edit body, or answer escalation |
| GET | `/escalations` | Unresolved in my scope |
| POST | `/tokens` | Mint token with role and scope |
| DELETE | `/tokens/{id}` | Revoke |

Errors: 401 bad token, 403 outside role, 404 unknown or hidden, 409 depth


## Tests - green from a clean state, no mocks

```
scripts/test_all.sh      # fresh volume, bootstrap, serve, test, stop
```

Unit: `uv run pytest server`
- Permissions module, pure, isolated

Integration: `PLANNER_ROOT_TOKEN=pln_... uv run pytest tests`
- Real HTTPS, real Postgres
- Every endpoint, every permission rule, every denial
- Depth limit proven by direct SQL insert, bypassing the API


## Read more

- `DEV_PLAN.md` - what is decided, what is built, what is next
- `agent-planning-system.md` - the full process and rules
- `skill/SKILL.md` - how an agent uses the server
