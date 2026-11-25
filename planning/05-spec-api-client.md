# Spec: api_client

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- Tree v5: `api_client/ one client for the HTTPS API, used by cli, web_ui, local_client` (`05-module-specs.md`)
- "PLEASE FIGHT THE CANCER OF MODERN DEVS PUTTING LOGIC IN UI" / Gradio "an HTTP client only, exactly like any other client" (`05-module-specs.md`, Round 2)
- "Drop the global server access token; per-principal credentials over TLS are enough. For the first version, use a locally self-signed certificate" (`05-module-specs.md`, "Phase 2: authentication")
- Contract: JSON, Bearer token, HTTPS; errors `NotFound`, `Forbidden`, `Invalid` mapped to 404/403/422; routes listed in `BUILD-PLAN.md`.
- "Don't reinvent wheels" (`CLAUDE.md`, `process-levels.md` "Module design").

## Module list

```
api_client/
  http_transport         one httpx.Client: base URL, Bearer header, TLS verify against the local cert, JSON in/out,
                         status -> contract errors (404 NotFound, 403 Forbidden, 422 Invalid, other -> ApiError)
  planning_api_client    Facade: one thin method per route; no logic beyond building the request
  client_settings        base URL, cert path, token source (env PLANNING_URL, PLANNING_CA_CERT, PLANNING_TOKEN)
```

Public: `PlanningApiClient`, `ClientSettings`, `ApiError`. `http_transport` stays private.

## Types

```python
@dataclass(frozen=True)
class ClientSettings:
    base_url: str                 # default https://127.0.0.1:<port>
    ca_cert_path: Path | None     # the server's self-signed cert; None = system trust
    token: str | None
    timeout_seconds: float = 30

class ApiError(Exception):        # unexpected status; carries status + body
    status: int; body: dict | str
```

Responses are returned as plain dicts (the JSON the server sent). No client-side models: the server owns the shapes.

## Public interface (one method per route in BUILD-PLAN.md)

```python
class PlanningApiClient:
    def __init__(self, settings: ClientSettings, transport=None)   # transport injectable for tests
    def with_token(self, token) -> "PlanningApiClient"
    # auth / identity
    def start_admin_session(self, password) -> dict      # POST /admin/sessions
    def me(self) -> dict                                  # GET /me
    def mint_credential(self, role, project_id, scope_node_id, agent_id) -> dict   # POST /credentials
    def mint_quote_key(self, install_label) -> dict       # POST /credentials/quote-key
    def revoke_credential(self, credential_id) -> dict    # POST /credentials/{id}/revoke
    def register_agent(self, agent_id, **metadata) -> dict  # POST /agents
    # tree
    def create_project(self, title, context_summary) -> dict
    def create_node(self, parent_id, title, level_label, context_summary, labels=(), depends_on=None, position=None) -> dict
    def get_node(self, node_id) / children(node_id) / ancestors(node_id) / ready_children(node_id) -> dict | list
    def update_node(self, node_id, **fields) / move_node(node_id, new_parent_id, position) / set_state(node_id, state)
    def assign(self, node_id, agent_id, branch) -> dict   # {node, worker_token}
    def create_supplementary_task(self, node_id, kind, title, context_summary) -> dict
    def add_content(self, node_id, text, tags) / replace_content(node_id, reference_id, text)
    def context(self, node_id) -> dict
    # reader + references
    def reader_load(self, *, url=None, file_path=None, search_terms=None, strategy=None, line_start=None, line_count=None) -> list
        # file_path is read and sent as file_name + file_base64
    def reader_toc(self, id) / reader_get(self, id, **params) / reader_search(self, terms, ids, **opts)
    def reader_json(self, id, flags) / reader_lines(self, id, start, end) / reader_cite(self, id, start_line, end_line)
    def get_reference(self, id, follow_superseded=False) / reference_lines(self, id, ...) / render_citation(self, citation)
    def store_user_exchange(self, session_id, user_message, pre_text) -> dict   # quote key only
    # guidance
    def guidance(self, role) / guidance_templates() / guidance_rules()
```

## External integration tests (server mocked with httpx.MockTransport)

1. Every method sends the documented method, path and JSON body, with `Authorization: Bearer <token>`.
2. 404/403/422 raise NotFound/Forbidden/Invalid; 500 raises ApiError with the body.
3. TLS verification uses the configured cert path (no `verify=False` unless the path is unset and the URL is localhost; see judgement in the build log).
4. `reader_load(file_path=...)` sends base64 of the exact file bytes and the file name.
5. No token is ever logged or included in an error message.
6. Against FastAPI's TestClient (real app, mocked domain), the client round-trips `/me`.
