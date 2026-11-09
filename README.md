# Agent Planning Server

Postgres-backed tree of workorders, task nodes, and attached docs, served over HTTPS, with role-scoped bearer tokens enforced server-side. Any agent with server access creates a workorder and becomes its planner: plans with the user, scaffolds the work, and delegates nodes to worker agents that can only see and write their own subtree. An admin session, approved by the user per session, maintains the knowledge bases and workorder visibility. Every write is mirrored to disk per workorder.

**What a workorder is.** A workorder is a feature, a sprint's worth of work, a larger tech spike, a broad research phase, or a fix. It is never used to fully encapsulate a large project, app, product, or long-term task. Those are defined in the product or company knowledge base by the admin agent, and updated through documents that planning or dev agents submit to an admin agent, who updates the central knowledge bases. Process and rules: `agent-planning-system.md`. Rules added at the start of every agent's session, before its custom instructions, by agent type: `agent_instruction_injections.json`. Design decisions: `PLAN.md`, `DEV_PLAN.md`. Agent usage: `skill/SKILL.md`.

**The planner is the workorder's admin.** Full stop. A planner token is always scoped to a whole workorder. Inside that workorder a planner edits any node or doc, including another planner's, controls every worker token, clears review flags, and sets state. Two planners on one workorder are two admins of it. A review that treats any of this as a defect is measuring against a model this system does not use. The global admin session does the same across all workorders plus the knowledge bases and visibility.

**Why the lanes exist.** Agents given the whole picture build what they imagine instead of what was planned. They wander into sibling modules, redefine interfaces, and invent context. The tokens, the scoped reads, and the read-only instruction docs exist to keep each agent on its own task with exactly the context it needs and nothing more. That is context control, not security. The lanes are a deadbolt, not a vault: they keep honest agents honest and make stepping out of lane an explicit act rather than a drift.

**Scope at this stage.** A local tool for one developer's machine, running next to an agent harness that can spawn multiple agents. An agent that reads the env file or the backups folder, or opens the admin login window uninvited, is breaking its rules, and the rules are the control. Isolating agents so they cannot is the user's choice, outside this app. There is no threat model beyond that, so the self-signed cert and `curl -k` are fine. It is not an internet service.

## Data model

- `nodes`: `id, parent_id, title, owner, state (open|blocked|done), needs_review, uuid, visible`. Single tree. Fixed children of root: `kb` (2), `plans` (3). A workorder is a direct child of `plans` with a uuid; a knowledge base is a direct child of `kb` with a uuid. Several of each may exist.
- `workorder_kbs`: which kbs a workorder may read. `workorder_visibility`: explicit grants to read a hidden workorder.
- `docs`: `id, node_id, role, body (markdown), author, answer, resolved`. Roles: `summary` (one per node), `instruction`, `environment`, `survey`, `approval`, `review`, `question` (planner-written); `report`, `spike`, `escalation`, `kb_proposal` (worker-written).
- `tokens`: `id, label, role (planner|worker), scope_node_id, parent_token_id, revoked, rotated_at`. Auth checks a hash; the plaintext is kept in `token_secrets`, readable by admin for any token and by a planner for its workorder's workers, so a lost session can be recovered without disrupting anything. Admin is not a token row: it is an in-memory session created by the browser login. The admin password is never stored in plaintext, only as a salted hash, and admin session tokens are never written to any table.
- `doc_versions`: every previous version of a doc, written by a trigger on update. Append-only; the audit trail. Nodes can be renamed, reparented within their workorder, and deleted by the workorder's planner or the admin; the depth rule applies to moves as well as inserts.

Depth is enforced by a `BEFORE INSERT` trigger: level 4 under `plans` sets `needs_review`, level 5 raises and the API returns 409. `kb` is exempt.

## Permissions

| | admin | planner | worker |
|---|---|---|---|
| read | everything | own workorder; other workorders that are visible or granted; every kb | scope subtree; ancestor `environment` docs; the kbs assigned to its workorder or overridden on an ancestor node |
| write docs | anywhere | any role in own workorder | `report`, `spike`, `escalation`, `kb_proposal` on scope subtree |
| edit docs | any | any in own workorder | docs it authored |
| create nodes | anywhere | in own workorder | beneath scope |
| set state, answer escalations | yes | in own workorder | no |
| mint tokens | planners, workers | workers in own workorder | no |
| create workorders | yes | yes, and any caller with the server access token | no |
| assign kbs to a workorder or node | yes | own workorder | no |
| hide a workorder, grant visibility | yes | no | no |
| write a kb, resolve `kb_proposal` | yes | no | no |

Every request also carries `X-Server-Access`, the value of `PLANNER_SERVER_ACCESS_TOKEN` in `.env`. Without it the server answers 401. `.env` is the one local file holding what disk access grants: the database password and the server access token, owner-only permissions.

Other workorders and ancestors return 404 to workers. Hidden workorders return 404 to planners without a grant. Rules live in `ai_project_planning_server/permissions.py`, pure, with unit tests.

## API

Bearer auth. JSON bodies. Self-signed cert by default.

| Method | Path | Body / returns |
|---|---|---|
| GET | `/me` | `role, scope_node_id, label` |
| POST | `/admin/nonce` | unauthenticated: start a login; returns a nonce |
| GET / POST | `/admin/login` | the browser page where the user types the admin password |
| GET | `/admin/session/{nonce}` | the session token, once, after a successful login |
| POST | `/admin/logout` | end the caller's admin session |
| POST | `/workorders` | `{title, summary}` → `{uuid, node_id, planner_token}`; no bearer needed |
| GET | `/workorders` | workorders the caller may read |
| PATCH | `/workorders/{uuid}` | `{kbs?: [uuid]}` own planner or admin; `{visible?}` admin |
| POST / DELETE | `/workorders/{uuid}/visibility` | admin: `{viewer: uuid}` grant or revoke read on a hidden workorder |
| POST | `/kbs` | admin: `{title, summary}` → kb with uuid |
| GET | `/kbs` | kbs the caller may read |
| GET | `/nodes/{id}` | node, docs, `environment` (ancestor env docs) |
| GET | `/nodes/{id}/tree` | nested `id, title, state` |
| POST | `/nodes` | `{parent_id, title, summary}`; level 4 adds `warning` |
| PATCH | `/nodes/{id}` | `{state}`, `{needs_review}`, `{title}`, `{parent_id}` (move within the workorder, depth rule applies), `{kbs: [uuid]}` (kb override for agents beneath) |
| DELETE | `/nodes/{id}` | planner or admin: delete the subtree; tokens beneath are revoked |
| GET | `/nodes/review` | nodes flagged `needs_review` in scope |
| POST | `/nodes/{id}/docs` | `{role, body}` |
| PATCH | `/docs/{id}` | `{body}`, or `{answer, resolved}` on `escalation` / `kb_proposal` |
| GET | `/docs/{id}/history` | previous versions, oldest first (planner, or the author) |
| GET | `/escalations` | unresolved escalations in scope |
| GET | `/proposals` | unresolved `kb_proposal` docs in scope |
| POST | `/tokens` | `{label, role, scope_node_id}` → plaintext token |
| GET | `/tokens` | tokens in scope (planner) |
| GET | `/tokens/{id}/secret` | the plaintext; admin for any, planner for its workers and itself |
| POST | `/tokens/{id}/rotate` | new plaintext, old one ends; same rights as secret |
| DELETE | `/tokens/{id}` | revoke; admin, or a planner in its workorder. Revocation cascades to tokens minted beneath |

Errors: 401 bad token, 403 role denies, 404 not found or not visible, 409 depth, 422 bad value.

## Run

```
uv sync --extra test
uv run ai-project-planning-server init-env     # .env (gitignored, owner-only): DB password and server access token, once per machine
docker compose up -d --wait          # Postgres 16 on 127.0.0.1:5433
uv run ai-project-planning-server bootstrap    # schema, root/kb/plans; the user sets the admin password interactively. SAVE IT: it cannot be recovered
                                               # an agent opens a terminal window on the user's desktop running this (e.g. gnome-terminal -- ...); the user types the password there; the agent never sees it
uv run ai-project-planning-server              # HTTPS on 127.0.0.1:8787; cert generated into certs/
uv run ai-project-planning-server admin-login  # opens a browser login window; the user types the password; prints a session ADMIN_TOKEN once
```

Server and database bind to localhost. No default passwords. Admin is a session: the password is known only to the user, the agent never sees it, and sessions live in server memory only, so a restart ends them. Admin is not needed to start work; any agent creates a workorder and gets its planner token in the response. Tokens keep agents in their lane; the server does not gate process steps such as `done` on reports or reviews. Roles and handoffs: `WORKFLOWS.md`.

Env: `PLANNER_DSN`, `PLANNER_PORT`, `PLANNER_HOST`, `PLANNER_CERT_DIR`, `PLANNER_BACKUP_DIR` (live export, default `backups/`), `PLANNER_FULL_BACKUP_DIR` (default `full_backups/`), `PLANNER_DB_PORT` (compose host port, default 5433), `PLANNER_SERVER_ACCESS_TOKEN` (overrides `.env`). Reset with `docker compose down -v`.

Other commands: `set-admin-password` (asks for the current password, re-encrypts the backup key), `backup`, `backups`, `restore <file>`, `init-backup-keys` (for a database bootstrapped before backups existed), `admin-login`, `admin-logout`.

Live export: every write under `plans` or `kb`, including workorder creation, rewrites that workorder's subtree to `PLANNER_BACKUP_DIR/<workorder-uuid>/` (kbs under `kb/<uuid>/`) as `tree.json`, `docs/<node>-<role>-<doc>.md`, and `.history.md` beside any doc that has been edited. Written to a temp dir and swapped in. Writes to one workorder are serialized. An export failure rolls the write back. This is a readable mirror, not the backup.

Backup: a full database dump, encrypted, taken every time a task node is set done, and on demand with `uv run ai-project-planning-server backup`. Files land in `full_backups/`. Retention after each backup: the oldest of each week and of each month are pinned; of everything else, task-triggered or on demand, the 10 latest are kept; the oldest of each day is also kept. Encryption uses a keypair created at bootstrap: the public key is stored in the clear and used at backup time, the private key is stored encrypted with the admin password and unlocked only on restore. Restore replaces the database: `uv run ai-project-planning-server restore <file>` asks for the admin password and a typed confirmation. A backup holds whatever was in the database, including anything later rolled back; that is the point. After a rollback for a severe security reason, stop work, take a new backup, then load and fix or purge older backups in turn. That is a note, not a routine.

First use: create a workorder. The response carries the workorder's planner token. No admin needed.

```
A="X-Server-Access: $(grep PLANNER_SERVER_ACCESS_TOKEN .env | cut -d= -f2)"
curl -sk https://localhost:8787/workorders -H "$A" \
  -H 'content-type: application/json' -d '{"title":"my workorder","summary":"..."}'
```

Knowledge bases are created by an admin session (`admin-login`, user types the password), then the planner chooses which ones its workorder uses.

## Process summary

1. Planner outlines with the user, one thread at a time. On an existing system: survey it, prove each claim with a real test, record a `survey` doc. Spikes only for what must be proven.
2. Formal plan: work, definition of done, flow and user story, interfaces, what changes vs is added, three bands (firm / design notes / dev discretion, each named), modules, names, formatting of every output and document. User approves the text as written on the server.
3. Plan written to the server: workorder node with `summary`, `instruction`, `environment`; one child per module.
4. Hollow skeleton: stubs, rails tests green, acceptance tests under strict xfail. Reference run against a throwaway implementation before commit.
5. Delegate: one worker token per node. Worker finishes its node, posts a `report`, stops. Escalation = blocked; the worker posts and stops.
6. Planner verifies against the definition of done, runs the standing-rules review (`review` doc), commits, revokes the token, sets `done`, starts dependents. A roadblock sets `blocked` and halts dependents until the user decides. Mocks exist only under an `approval` doc.

## Tests

```
uv run python scripts/test_all.py    # clean volume, bootstrap, serve, pytest, stop
uv run pytest ai_project_planning_server                 # permissions unit tests only
```

Integration tests run over real HTTPS against real Postgres: every endpoint, every permission rule and denial, depth trigger via direct SQL, backup files on every write, revocation cascade. The runner uses its own compose project with a random per-run name, its own DB port, and a temp dir for secrets, backups, and the log, so the live database is never touched and parallel runs do not collide. It refuses to start if `PLANNER_PORT` is in use. Needs docker compose, uv, Python 3.10+. Verified on Linux; macOS and Windows untested.

## Customization

Agent rules live in `agent_instruction_injections.json`. Each entry has an `id`, an `applies_to` list of agent types (`admin`, `planner`, `worker`), and the rule `text`. The blocks that apply to an agent's type are added at the start of its session, before its custom instructions, by whoever starts the session. Add, edit, or remove rules there; no code change is needed.

## Layout

```
ai_project_planning_server/   app.py permissions.py schema.sql bootstrap.py db.py tls.py __main__.py
tests/    test_api.py
skill/    SKILL.md
scripts/  test_all.py
```
