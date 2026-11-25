# Spec: web_ui

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

**Not in the first build** (BUILD-DECISIONS-LOG #7). Specced now so the scaffold can include it hollow.

A Gradio app that is only a view: it calls the HTTPS API through `api_client` and shows what comes back. No business logic, no database access, no rules.

## Recorded decisions this builds on

- "**A Gradio UI that is only a UI.** Every action, including the user's own actions, can be done directly through the HTTP interface and the CLI. User: \"stick with gradio for the ui. It's also essential that the ui remain simply the ui, DO NOT PUT BUSINESS LOGIC IN THE WEB/GRADOI/UI CODE - REMEMBER THAT THERE'S A CLI AND HTTP INTERFACE THAT MUST DO EVERYTHING DIRECTLY - EVEN USER ACTIONS.\"" (`02-definition-of-done.md`, 17)
- "**Gradio:** an HTTP client only, exactly like any other client." and User: "one more reason to have the web interface not contain business logic AT ALL - PLEASE FIGHT THE CANCER OF MODERN DEVS PUTTING LOGIC IN UI PLEASE PLEASE PLEASE" (`05-module-specs.md`, Round 2)
- "**`web_ui`: generic pages** (node list filtered by state, node detail, login), on the user's condition: \"as long as it's truly no logic, and the interface the https gradio web client uses is also usable the same way by an admin agent (i.e. mcp), so no function of the website can depend on the actual website - true mvc\"." (Round 5)
- Tree v5: `web_ui/` with `gradio_application`, `pages/node_list_page` ("filtered by state"), `node_detail_page`, `login_page`; `api_client/` "used by cli, web_ui, local_client"; `admin_login/` "the password popup that starts an admin session (cli, web_ui, agent)".
- Admin sessions: "a popup asks the human for a password only they know" (Recheck 13). The approval mechanism for unsupported harnesses: "the user approves or adds notes on the website, and that is recorded as a user response" (Phase 2: references, 5).
- Node states: assigned, in progress, done, abandoned (Phase 2: project_tree, 1).

## Nested modules

```
web_ui/
  gradio_application    builds the Gradio Blocks app from the pages; holds the session's api_client; launches
  pages/
    login_page          password field -> POST /admin/sessions -> keeps the token for this browser session
    node_list_page      state filter -> GET of nodes by state -> table; row click opens the detail page
    node_detail_page    GET /nodes/{id}, /children, /context; actions are buttons that each call one route
```

Each page is a small class that takes an `ApiClient` and returns Gradio components with handlers. A handler does exactly: read inputs -> one `api_client` call -> render the response. Any choice of what is allowed, valid or next comes from the server's response (e.g. allowed actions, 403/422 messages shown as returned).

## Types

None of its own. It uses `api_client`'s request/response types and shows server errors verbatim.

## Public interface

```python
class WebUserInterface:
    def __init__(self, config: WebUiConfig, api_client_factory: Callable[[str], ApiClient])
    def launch(self) -> None            # gradio Blocks.launch on config.host:config.port

@dataclass(frozen=True)
class WebUiConfig:
    server_url: str                     # the HTTPS API
    host: str = "127.0.0.1"
    port: int
    ca_certificate: Path | None         # the local self-signed cert, for api_client

class LoginPage / NodeListPage / NodeDetailPage:
    def __init__(self, api_client: ApiClient)
    def build(self) -> gradio.Blocks    # components + handlers; no other public methods
```

`main.py` loads it as the generic "user interface" with its own config section (Recheck 12).

## Routes it uses (all existing; none added for the UI)

`POST /admin/sessions`, `GET /me`, node reads (`GET /nodes/{id}`, `/children`, `/ancestors`, `/context`, nodes by state), `POST /nodes/{id}/state`, `POST /nodes/{id}/content`, `GET /references/{id}`, `POST /references/render`. If a page needs data no route gives, a route (and command) is added on the server, never computed in the UI.

## External integration tests (mock up front)

Mocks: a fake `ApiClient` recording calls and returning canned responses.

1. Every handler makes exactly one `api_client` call per user action, and the rendered output is the response's data unchanged.
2. Login: a password goes to `POST /admin/sessions`; the returned token is used on later calls; a 403 is shown as returned.
3. Node list: choosing a state sends that state to the server; filtering is never done in the UI.
4. Node detail: a state change calls `POST /nodes/{id}/state`; a server refusal is shown, the page does not pre-check it.
5. Parity: for each page action, the same call through `cli`/`api_client` as an admin agent yields the same server result (true MVC).
6. Static check: `web_ui/` imports nothing from `server/`, `storage/` or SQLAlchemy.
