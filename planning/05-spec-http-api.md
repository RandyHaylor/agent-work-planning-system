# Spec: http_api

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- Tree v5: `http_api/` "protocol only": `application` "FastAPI wiring, TLS (carried)", `credential_dependency`, `command_routes` "every route -> a command", `error_mapping` (05-module-specs.md).
- "Drop the global server access token; per-principal credentials over TLS are enough. For the first version, use a locally self-signed certificate and don't worry about it beyond that." (Phase 2: authentication, 1).
- "No business logic in any UI ... The HTTPS interface does everything" (CLAUDE.md); "our https interface is already LIKE a mcp server" (Round 2).
- Shared contract: `current_principal() -> Principal` (Bearer token), `db_connection()`; each serving module exposes `router` from `<module>/http_routes.py`; http_api mounts `/` core, `/reader` + `/references`, `/guidance`; NotFound/Forbidden/Invalid -> 404/403/422 (BUILD-PLAN.md).
- "Just our scenario matters now - this local host, claude cli harness adapter" (BUILD-DECISIONS-LOG header).

## Modules (nested)

```
server/http_api/                     public: create_app(section, runner, authenticator) -> FastAPI; serve(app, section)
  application                        builds the FastAPI app, installs error mapping, mounts routers
  tls                                ensure_self_signed_cert(cert_dir) -> (cert, key); carried from ai_project_planning_server/tls.py
                                     (RSA 2048, CN/SAN localhost + 127.0.0.1, 10 years, key 0600)
  dependencies                       current_principal, command_runner (contract names; exists as stubs)
  credential_dependency              Bearer header -> CredentialAuthenticator.authenticate -> Principal
  error_mapping                      DomainError subclasses -> status + {"error": kind, "detail": message}
  command_routes                     core routes (table in 05-spec-commands.md): parse body -> build command -> runner.run -> JSON
  router_mounting                    mounts each router named in config at its prefix
```

## Types

```python
class RouterSpec:  prefix: str; router: APIRouter       # from config: {"prefix": "/reader", "router": "pkg.module:router"}

ERROR_STATUS = {NotFound: 404, Forbidden: 403, Invalid: 422}   # any other exception -> 500, no internals in body
```

Pydantic request/response models live beside the routes that use them (protocol only); domain dataclasses are converted at the edge.

## Public interface

```python
def create_app(section: ConfigSection, runner: CommandRunner, authenticator: CredentialAuthenticator) -> FastAPI
def serve(app: FastAPI, section: ConfigSection) -> None      # uvicorn on section host (default 127.0.0.1) and port, ssl from tls
```

`run` (from the server component) = create_storage -> build CommandRunner -> create_app -> serve.

Route handlers in every module router (core, reader/references, guidance) do only: read request, build a command, `runner.run(command, principal)`, return JSON. No domain call, no SQL.

## OPEN CONFLICT (not resolved here)

`dependencies.db_connection()` (shared contract: "one transaction per request; read-only for GET") vs the recorded decision that `CommandRunner` opens the transaction ("permission check -> transaction (read-only for reads) -> run"). Both can't own it. This spec assumes routers depend on a `command_runner()` dependency and do not use `db_connection`; the lead decides whether to drop `db_connection` from the contract.

## External integration tests (mocked CommandRunner and CredentialAuthenticator; FastAPI TestClient)

1. Each route in 05-spec-commands.md hands the matching command class (with parsed fields) and the authenticated principal to the runner.
2. Missing or unknown Bearer token -> 403 (except POST /admin/sessions, which needs none).
3. NotFound / Forbidden / Invalid raised by the runner -> 404 / 403 / 422 with `{"error", "detail"}`; an unexpected error -> 500 without a traceback in the body.
4. Bad request body -> 422.
5. Routers named in config are mounted at their prefixes (`/reader`, `/references`, `/guidance`).
6. `ensure_self_signed_cert` creates cert and key once, reuses them on the second call, key mode 0600, SAN includes localhost and 127.0.0.1.
7. `serve` binds 127.0.0.1 by default with the TLS files (uvicorn mocked).
8. No `X-Server-Access` header is required or read.
