# Agent Planning Server

Postgres-backed tree of plan nodes and attached docs, served over HTTPS, with role-scoped bearer tokens enforced server-side. A planner agent plans with the user, scaffolds the work, and delegates nodes to worker agents that can only see and write their own subtree. Process and rules: `agent-planning-system.md`. Design decisions: `PLAN.md`, `DEV_PLAN.md`. Agent usage: `skill/SKILL.md`.

## Data model

- `nodes`: `id, parent_id, title, owner, state (open|blocked|done), needs_review`. Single tree. Fixed children of root: `kb` (2), `plans` (3). A project is a direct child of `plans`.
- `docs`: `id, node_id, role, body (markdown), author, answer, resolved`. Roles: `summary` (one per node), `instruction`, `environment`, `report`, `spike`, `escalation`, `question`, `kb_proposal`.
- `tokens`: `id, label, role (planner|worker), scope_node_id, parent_token_id, revoked`. Stored hashed. Plaintext returned once at mint.

Depth is enforced by a `BEFORE INSERT` trigger: level 4 under `plans` sets `needs_review`, level 5 raises and the API returns 409. `kb` is exempt.

## Permissions

| | planner | worker |
|---|---|---|
| read | scope subtree + ancestors + `kb` | scope subtree + `kb` + `environment` docs on ancestors |
| write docs | any role, any node in scope | `report`, `spike`, `escalation`, `kb_proposal` on scope subtree |
| edit docs | any in scope | own docs only |
| create nodes | in scope | beneath scope |
| set state, answer escalations | yes | no |
| mint / revoke tokens | in scope | no |
| write `kb` | root only | no |

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
| DELETE | `/tokens/{id}` | revoke |

Errors: 401 bad token, 403 role denies, 404 not found or not visible, 409 depth, 422 bad value.

## Run

```
docker compose up -d                 # Postgres 16 on 5433
uv sync --extra test
uv run python -m server bootstrap    # schema, root/kb/plans, prints ROOT_TOKEN once
uv run python -m server              # HTTPS on 8787; cert generated into certs/
```

Env: `PLANNER_DSN`, `PLANNER_PORT`, `PLANNER_HOST`, `PLANNER_CERT_DIR`. Reset with `docker compose down -v`.

First use: mint a planner token scoped to `plans` with the root token, then work with that.

```
curl -sk https://localhost:8787/tokens -H "Authorization: Bearer $ROOT_TOKEN" \
  -H 'content-type: application/json' -d '{"label":"planner","role":"planner","scope_node_id":3}'
```

## Process summary

1. Planner outlines with the user, one thread at a time. Spikes only for what must be proven.
2. Formal plan: work, definition of done, interfaces, three bands (firm / design notes / dev discretion, each named), modules, names, formatting of every output and document.
3. Plan written to the server: project node with `summary`, `instruction`, `environment`; one child per module.
4. Hollow skeleton: stubs, rails tests green, acceptance tests under strict xfail. Reference run against a throwaway implementation before commit.
5. Delegate: one worker token per node. Worker finishes its node, posts a `report`, stops. Escalation = blocked; the worker posts and stops.
6. Planner verifies against the definition of done, commits, revokes the token, sets `done`, starts dependents.

## Tests

```
uv run python scripts/test_all.py    # clean volume, bootstrap, serve, pytest, stop
uv run pytest server                 # permissions unit tests only
```

Integration tests run over real HTTPS against real Postgres: every endpoint, every permission rule and denial, depth trigger via direct SQL. Runner is Python and needs docker compose, uv, Python 3.10+. Verified on Linux; macOS and Windows untested.

## Layout

```
server/   app.py permissions.py schema.sql bootstrap.py db.py tls.py __main__.py
tests/    test_api.py
skill/    SKILL.md
scripts/  test_all.py
```
