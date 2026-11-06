# Agent Planning Server

Postgres-backed tree of plan nodes and attached docs, served over HTTPS, with role-scoped bearer tokens enforced server-side. A planner agent plans with the user, scaffolds the work, and delegates nodes to worker agents that can only see and write their own subtree. Every write is mirrored to disk per project. Process and rules: `agent-planning-system.md`. Design decisions: `PLAN.md`, `DEV_PLAN.md`. Agent usage: `skill/SKILL.md`.

**Scope at this stage.** A local tool for one developer's machine, running next to an agent harness that can spawn multiple agents. Tokens are lane-keeping, not security: they stop a dev agent from reading or writing outside its node. There is no threat model beyond that, so the self-signed cert and `curl -k` are fine. It is not an internet service.

## Data model

- `nodes`: `id, parent_id, title, owner, state (open|blocked|done), needs_review`. Single tree. Fixed children of root: `kb` (2), `plans` (3). A project is a direct child of `plans`.
- `docs`: `id, node_id, role, body (markdown), author, answer, resolved`. Roles: `summary` (one per node), `instruction`, `environment`, `survey`, `approval`, `review`, `question` (planner-written); `report`, `spike`, `escalation`, `kb_proposal` (worker-written).
- `tokens`: `id, label, role (planner|worker), scope_node_id, parent_token_id, revoked`. Stored hashed. Plaintext returned once at mint.

Depth is enforced by a `BEFORE INSERT` trigger: level 4 under `plans` sets `needs_review`, level 5 raises and the API returns 409. `kb` is exempt.

## Permissions

| | planner | worker |
|---|---|---|
| read | everything: `plans`, `kb`, all projects | scope subtree + `kb` + `environment` docs on ancestors |
| write docs | any role, any node | `report`, `spike`, `escalation`, `kb_proposal` on scope subtree |
| edit docs | any | docs it authored |
| create nodes | in scope | beneath scope |
| set state, answer escalations | yes | no |
| mint / revoke tokens | in scope | no |
| write `kb` | yes, after user approval of a `kb_proposal` | no |

Ancestor nodes return 404 to workers. Rules live in `server/permissions.py`, pure, with unit tests.

## API

Bearer auth. JSON bodies. Self-signed cert by default.

| Method | Path | Body / returns |
|---|---|---|
| GET | `/me` | `role, scope_node_id, label` |
| GET | `/nodes/{id}` | node, docs, `environment` (ancestor env docs) |
| GET | `/nodes/{id}/tree` | nested `id, title, state` |
| POST | `/nodes` | `{parent_id, title, summary}`; level 4 adds `warning` |
| PATCH | `/nodes/{id}` | `{state}` |
| POST | `/nodes/{id}/docs` | `{role, body}` |
| PATCH | `/docs/{id}` | `{body}` or `{answer, resolved}` |
| GET | `/escalations` | unresolved escalations in scope |
| POST | `/tokens` | `{label, role, scope_node_id}` → plaintext token |
| GET | `/tokens` | tokens in scope (planner) |
| DELETE | `/tokens/{id}` | revoke; any planner whose scope contains the token's scope. Revocation cascades to tokens minted beneath |

Errors: 401 bad token, 403 role denies, 404 not found or not visible, 409 depth, 422 bad value.

## Run

```
uv sync --extra test
uv run python -m server init-env     # random DB password into .env (gitignored), once per machine
docker compose up -d --wait          # Postgres 16 on 127.0.0.1:5433
uv run python -m server bootstrap    # schema, root/kb/plans, prints ROOT_TOKEN once
uv run python -m server              # HTTPS on 127.0.0.1:8787; cert generated into certs/
```

Server and database bind to localhost. No default password. The planner is the admin: it sees and writes everything. Tokens keep workers in their lane; the server does not gate process steps such as `done` on reports or reviews.

Env: `PLANNER_DSN`, `PLANNER_PORT`, `PLANNER_HOST`, `PLANNER_CERT_DIR`, `PLANNER_BACKUP_DIR` (default `backups/`), `PLANNER_DB_PORT` (compose host port, default 5433). Reset with `docker compose down -v`.

Backup: every write under `plans` or `kb` rewrites that project's subtree to `PLANNER_BACKUP_DIR/<project-id>-<slug>/` as `tree.json` plus `docs/<node>-<role>-<doc>.md`. Writes to one project are serialized, so backups run one at a time and later writes wait. A backup failure rolls the write back.

First use: mint a planner token scoped to `plans` with the root token, then work with that.

```
curl -sk https://localhost:8787/tokens -H "Authorization: Bearer $ROOT_TOKEN" \
  -H 'content-type: application/json' -d '{"label":"planner","role":"planner","scope_node_id":3}'
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
uv run pytest server                 # permissions unit tests only
```

Integration tests run over real HTTPS against real Postgres: every endpoint, every permission rule and denial, depth trigger via direct SQL, backup files on every write, revocation cascade. The runner uses its own compose project `planner-test` on DB port 5434 and a temp backup dir, so the live database is never touched. It refuses to start if `PLANNER_PORT` is in use. Needs docker compose, uv, Python 3.10+. Verified on Linux; macOS and Windows untested.

## Layout

```
server/   app.py permissions.py schema.sql bootstrap.py db.py tls.py __main__.py
tests/    test_api.py
skill/    SKILL.md
scripts/  test_all.py
```
