# Agent Planning Server

Postgres-backed tree of projects, plan nodes, and attached docs, served over HTTPS, with role-scoped bearer tokens enforced server-side. An admin agent maintains the knowledge bases and creates projects. A planner agent runs one project: plans with the user, scaffolds the work, and delegates nodes to worker agents that can only see and write their own subtree. Every write is mirrored to disk per project. Process and rules: `agent-planning-system.md`. Rules added at the start of every agent's session, before its custom instructions, by agent type: `agent_instruction_injections.json`. Design decisions: `PLAN.md`, `DEV_PLAN.md`. Agent usage: `skill/SKILL.md`.

**Scope at this stage.** A local tool for one developer's machine, running next to an agent harness that can spawn multiple agents. Tokens are lane-keeping, not security: they stop a dev agent from reading or writing outside its node. There is no threat model beyond that, so the self-signed cert and `curl -k` are fine. It is not an internet service.

## Data model

- `nodes`: `id, parent_id, title, owner, state (open|blocked|done), needs_review, uuid, visible`. Single tree. Fixed children of root: `kb` (2), `plans` (3). A project is a direct child of `plans` with a uuid; a knowledge base is a direct child of `kb` with a uuid. Several of each may exist.
- `project_kbs`: which kbs a project may read. `project_visibility`: explicit grants to read a hidden project.
- `docs`: `id, node_id, role, body (markdown), author, answer, resolved`. Roles: `summary` (one per node), `instruction`, `environment`, `survey`, `approval`, `review`, `question` (planner-written); `report`, `spike`, `escalation`, `kb_proposal` (worker-written).
- `tokens`: `id, label, role (planner|worker), scope_node_id, parent_token_id, revoked`. Stored hashed. Plaintext returned once at mint. Admin is not a token row: it is an in-memory session created by the browser login.
- `doc_versions`: every previous version of a doc, written by a trigger on update. Append-only; the audit trail. Nodes are immutable: no delete, rename, or reparent.

Depth is enforced by a `BEFORE INSERT` trigger: level 4 under `plans` sets `needs_review`, level 5 raises and the API returns 409. `kb` is exempt.

## Permissions

| | admin | planner | worker |
|---|---|---|---|
| read | everything | own project; other projects that are visible or granted; assigned kbs | scope subtree; ancestor `environment` docs; assigned kbs |
| write docs | anywhere | any role in own project | `report`, `spike`, `escalation`, `kb_proposal` on scope subtree |
| edit docs | any | any in own project | docs it authored |
| create nodes | anywhere | in own project | beneath scope |
| set state, answer escalations | yes | in own project | no |
| mint tokens | planners, workers | workers in own project | no |
| create projects, assign kbs, set visibility | yes | no | no |
| write a kb, resolve `kb_proposal` | yes | no | no |

Other projects and ancestors return 404 to workers. Hidden projects return 404 to planners without a grant. Rules live in `ai_project_planning_server/permissions.py`, pure, with unit tests.

## API

Bearer auth. JSON bodies. Self-signed cert by default.

| Method | Path | Body / returns |
|---|---|---|
| GET | `/me` | `role, scope_node_id, label` |
| POST | `/admin/nonce` | unauthenticated: start a login; returns a nonce |
| GET / POST | `/admin/login` | the browser page where the user types the admin password |
| GET | `/admin/session/{nonce}` | the session token, once, after a successful login |
| POST | `/admin/logout` | end the caller's admin session |
| POST | `/projects` | admin: `{title, summary}` → `{uuid, node_id, planner_token}` |
| GET | `/projects` | projects the caller may read |
| PATCH | `/projects/{uuid}` | admin: `{visible?, kbs?: [uuid]}` |
| POST / DELETE | `/projects/{uuid}/visibility` | admin: `{viewer: uuid}` grant or revoke read on a hidden project |
| POST | `/kbs` | admin: `{title, summary}` → kb with uuid |
| GET | `/kbs` | kbs the caller may read |
| GET | `/nodes/{id}` | node, docs, `environment` (ancestor env docs) |
| GET | `/nodes/{id}/tree` | nested `id, title, state` |
| POST | `/nodes` | `{parent_id, title, summary}`; level 4 adds `warning` |
| PATCH | `/nodes/{id}` | `{state}` and/or `{needs_review}` |
| GET | `/nodes/review` | nodes flagged `needs_review` in scope |
| POST | `/nodes/{id}/docs` | `{role, body}` |
| PATCH | `/docs/{id}` | `{body}`, or `{answer, resolved}` on `escalation` / `kb_proposal` |
| GET | `/docs/{id}/history` | previous versions, oldest first (planner, or the author) |
| GET | `/escalations` | unresolved escalations in scope |
| GET | `/proposals` | unresolved `kb_proposal` docs in scope |
| POST | `/tokens` | `{label, role, scope_node_id}` → plaintext token |
| GET | `/tokens` | tokens in scope (planner) |
| DELETE | `/tokens/{id}` | revoke; any planner whose scope contains the token's scope. Revocation cascades to tokens minted beneath |

Errors: 401 bad token, 403 role denies, 404 not found or not visible, 409 depth, 422 bad value.

## Run

```
uv sync --extra test
uv run ai-project-planning-server init-env     # random DB password into .env (gitignored), once per machine
docker compose up -d --wait          # Postgres 16 on 127.0.0.1:5433
uv run ai-project-planning-server bootstrap    # schema, root/kb/plans; the user sets the admin password interactively
uv run ai-project-planning-server              # HTTPS on 127.0.0.1:8787; cert generated into certs/
uv run ai-project-planning-server admin-login  # opens a browser login window; the user types the password; prints a session ADMIN_TOKEN once
```

Server and database bind to localhost. No default passwords. Admin is a session: the password is known only to the user, the agent never sees it, and sessions live in server memory only, so a restart ends them. The admin session creates kbs and projects; each project's planner token is minted at project creation. Tokens keep agents in their lane; the server does not gate process steps such as `done` on reports or reviews. Roles and handoffs: `WORKFLOWS.md`.

Env: `PLANNER_DSN`, `PLANNER_PORT`, `PLANNER_HOST`, `PLANNER_CERT_DIR`, `PLANNER_BACKUP_DIR` (default `backups/`), `PLANNER_DB_PORT` (compose host port, default 5433). Reset with `docker compose down -v`.

Backup: every write under `plans` or `kb`, including project creation, rewrites that project's subtree to `PLANNER_BACKUP_DIR/<project-uuid>/` (kbs under `kb/<uuid>/`) as `tree.json`, `docs/<node>-<role>-<doc>.md`, and `.history.md` beside any doc that has been edited. Written to a temp dir and swapped in. Writes to one project are serialized, so backups run one at a time and later writes wait. A backup failure rolls the write back.

First use: create a kb and a project with the admin token. The response carries the project's planner token.

```
curl -sk https://localhost:8787/kbs -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'content-type: application/json' -d '{"title":"product","summary":"..."}'
curl -sk https://localhost:8787/projects -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'content-type: application/json' -d '{"title":"my project","summary":"..."}'
```

## Process summary

1. Planner outlines with the user, one thread at a time. On an existing system: survey it, prove each claim with a real test, record a `survey` doc. Spikes only for what must be proven.
2. Formal plan: work, definition of done, flow and user story, interfaces, what changes vs is added, three bands (firm / design notes / dev discretion, each named), modules, names, formatting of every output and document. User approves the text as written on the server.
3. Plan written to the server: project node with `summary`, `instruction`, `environment`; one child per module.
4. Hollow skeleton: stubs, rails tests green, acceptance tests under strict xfail. Reference run against a throwaway implementation before commit.
5. Delegate: one worker token per node. Worker finishes its node, posts a `report`, stops. Escalation = blocked; the worker posts and stops.
6. Planner verifies against the definition of done, runs the standing-rules review (`review` doc), commits, revokes the token, sets `done`, starts dependents. A roadblock sets `blocked` and halts dependents until the user decides. Mocks exist only under an `approval` doc.

## Tests

```
uv run python scripts/test_all.py    # clean volume, bootstrap, serve, pytest, stop
uv run pytest ai_project_planning_server                 # permissions unit tests only
```

Integration tests run over real HTTPS against real Postgres: every endpoint, every permission rule and denial, depth trigger via direct SQL, backup files on every write, revocation cascade. The runner uses its own compose project `planner-test` on DB port 5434 and a temp backup dir, so the live database is never touched. It refuses to start if `PLANNER_PORT` is in use. Needs docker compose, uv, Python 3.10+. Verified on Linux; macOS and Windows untested.

## Customization

Agent rules live in `agent_instruction_injections.json`. Each entry has an `id`, an `applies_to` list of agent types (`admin`, `planner`, `worker`), and the rule `text`. The blocks that apply to an agent's type are added at the start of its session, before its custom instructions, by whoever starts the session. Add, edit, or remove rules there; no code change is needed.

## Layout

```
ai_project_planning_server/   app.py permissions.py schema.sql bootstrap.py db.py tls.py __main__.py
tests/    test_api.py
skill/    SKILL.md
scripts/  test_all.py
```
