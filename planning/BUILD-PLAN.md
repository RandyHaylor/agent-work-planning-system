# Build plan: first usable version (local host + Claude Code CLI)

## Order (the system's own process; user, 2026-11-25)

1. **Level 5 finish:** a spec for every remaining module (`planning/05-spec-<module>.md`), built only on recorded decisions.
2. **Level 6 scaffold:** hollow modules with real interfaces and types for every module, plus external integration tests against mocks, all passing on mocks. Checked against the specs.
3. **Level 7 build:** workers fill the hollow modules in parallel until the integration tests pass on real implementations. No stopping for questions; issues go to `planning/BUILD-ISSUES.md` for the end.

The planner starts and stops tasks; for a very large task it spawns a dev manager (also a planner) to stay high level. Build modularly; no monoliths.

Specs: `planning/05-spec-*.md`, module tree v5 in `05-module-specs.md`, decisions there and in `process-levels.md`. Design rules: "Module design" in `process-levels.md` (commandments; never mix levels of detail). Calls made during the build: `BUILD-DECISIONS-LOG.md`.

## Package layout (all under `planning_system/`)

```
planning_system/
  main.py                       generic startup; reads config; mounts routers (lead integrates)
  configuration/                loads config/*.json; hands each module its section
  server/
    domain/
      access/                   Principal, PermissionPolicy               (spec: 05-spec-access.md)
      authentication/           hashing, issuer, authenticator, admin sessions (05-spec-authentication.md)
      agent_registry/           (05-spec-agent-registry.md)
      project_tree/             (05-spec-project-tree.md)
      context_assembly/         (05-spec-context-assembly.md)
      references/               ReferenceLibrary, temp cache, citations   (05-spec-references-and-reader.md)
    storage/                    SQLAlchemy Core stores; shared metadata in storage/metadata.py; Alembic
    commands/                   CommandRunner, request authorizer, command classes
    http_api/                   FastAPI app, TLS, dependencies, error mapping; mounts module routers
    bootstrap/                  first-time setup
  document_extraction/          decoding, content type, fallback runner, strategies
  fastreader/                   our copy of ai-agent-fastReader (adapted: cache -> temp cache store; cite)
  quick_json_reader/            our copy (JavaScript, run with Node)
  prompt_builder/               our copy of ai-rule-builder (Python package, data, tests, website)
  api_client/                   HTTPS client used by cli and local_client
  cli/                          thin hand-written wrapper over api_client (`planning` command)
  local_client/                 quote capture (SoT copy) + reference sync + Claude Code adapter
tests/planning_system/          tests per module
```

## Shared contract (fixed before parallel work; in `planning_system/contract.py` and `server/http_api/dependencies.py`)

- `Principal(agent_id, role, project_id, scope_node_id)`; roles `admin`, `planner`, `worker`, `quote_client`.
- FastAPI dependencies: `current_principal() -> Principal` (Bearer token), `db_connection() -> sqlalchemy Connection` (one transaction per request; read-only for GET).
- Each module that serves HTTP exposes `router: APIRouter` from `<module>/http_routes.py`. http_api mounts: `/` core, `/reader` + `/references` (references), `/guidance` (prompt_builder).
- Tables: every module declares tables on `planning_system.server.storage.metadata.METADATA`.
- Errors: raise `planning_system.contract.NotFound`, `Forbidden`, `Invalid`; http_api maps them to 404/403/422.

## HTTP routes (JSON; Bearer token; HTTPS with a local self-signed cert)

Core server (worktree A):
- `POST /admin/sessions` {password} -> {token} (the admin_login popup calls this; human types the password)
- `GET /me`
- `POST /credentials` {role: planner|worker, project_id, scope_node_id, agent_id} -> {token}; `POST /credentials/quote-key` {install_label} -> {token}; `POST /credentials/{id}/revoke`
- `POST /agents` {agent_id, host, platform, model, path, system, url} (register / update)
- `POST /projects` {title, context_summary} -> node (level "what we're doing")
- `POST /nodes` {parent_id, title, level_label, context_summary, labels, depends_on, position} -> node
- `GET /nodes/{id}`, `GET /nodes/{id}/children`, `GET /nodes/{id}/ancestors`, `GET /nodes/{id}/ready-children`
- `PATCH /nodes/{id}`, `POST /nodes/{id}/move`, `POST /nodes/{id}/state` {state}, `POST /nodes/{id}/assign` {agent_id, branch} -> {node, worker_token}
- `POST /nodes/{id}/supplementary` {kind: tech_spike|requirement_request, title, context_summary} (worker on its own task)
- `POST /nodes/{id}/content` {text, tags}; `PUT /nodes/{id}/content/{reference_id}` {text}
- `GET /nodes/{id}/context` -> assembled context

References + reader (worktree B):
- `POST /reader/load` {url | file_name + file_base64 | search_terms, strategy?, line_start?, line_count?} -> [{cache_id, toc, strategy_used, metadata}]
- `GET /reader/{id}/toc`, `GET /reader/{id}/get`, `POST /reader/search` {terms, ids, ...}, `POST /reader/{id}/json` {flags}, `GET /reader/{id}/lines?start=&end=`  (id = temp cache id or reference id)
- `POST /reader/cite` {id, start_line, end_line} -> {reference_id, citation}
- `GET /references/{id}` (?follow_superseded), `GET /references/{id}/lines`, `POST /references/render` {citation}
- `POST /references/user-exchange` {session_id, user_message, pre_text} (quote key only) -> {reference_id}

Prompt builder (worktree D):
- `GET /guidance/{role}` -> {role, template, text}; `GET /guidance/templates`, `GET /guidance/rules`
- `planning guidance-editor` launches its website locally for the user (presets saved with the server's files)

Client side (worktree C) uses the routes above; tests mock the server.

## Definition of done for this build

1. `docker compose up` + `planning-server bootstrap` + `planning-server run` start the new server over HTTPS on localhost.
2. From Claude Code: install the local client hooks; prompts are captured locally; `planning` CLI can create a project, add nodes, assign, load a URL/file into the reader, toc/search/get, cite (syncing a local user exchange when cited), and read assembled context and role guidance.
3. Tests for each module pass; an end-to-end smoke test runs walkthrough-1-style steps against a live local server.
