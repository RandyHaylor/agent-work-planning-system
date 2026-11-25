# Spec: admin_login

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- "Agent acting as the user is admin. The agent uses an admin session, obtained the same way (the user types the password in a login window), and can do everything admin can." (`05-module-specs.md`, Round 2, 1)
- "Admin sessions are temporary: a popup asks the human for a password only they know, and then an agent can act as admin. Keep that pattern; I like patterns that keep agents out of something no matter what they do." (`05-module-specs.md`, Recheck 13)
- Tree v5: `admin_login/ the password popup that starts an admin session (cli, web_ui, agent)`
- Route: `POST /admin/sessions {password} -> {token}` "(the admin_login popup calls this; human types the password)" (`BUILD-PLAN.md`)
- Carried code: `ai_project_planning_server/admin_cli.py` `login()` opens a server login page in the browser (nonce), polls until the human approves, prints `ADMIN_TOKEN=...`; `logout()` ends the session.

## Design

A small local window (Python `tkinter`, stdlib, masked entry) that the CLI opens on the user's desktop. The human types the password; the window POSTs it via `api_client.start_admin_session`; the token goes to the caller. The password never passes through the agent's stdin, arguments, environment or transcript. If no display is available it fails with a clear error (no terminal fallback: a terminal prompt would be typed into by the agent).

**FLAGGED conflict:** the carried pattern is a *server-hosted browser page* with nonce polling (password never reaches the client process); `BUILD-PLAN.md` routes the password through `POST /admin/sessions` from a local popup. This spec follows BUILD-PLAN; both keep the agent out.

## Module list

```
admin_login/
  password_prompt_window   tkinter masked-entry window; returns the typed string or None (cancel); no I/O beyond the window
  admin_login_flow         prompt -> api_client.start_admin_session -> token; retries on wrong password up to 3 times
```

## Public interface

```python
class AdminLoginFlow:
    def __init__(self, api: PlanningApiClient, prompt: PasswordPrompt)
    def login(self) -> str          # admin session token; raises LoginCancelled / LoginFailed / NoDisplay

class PasswordPrompt(Protocol):     # the window; a fake in tests
    def ask(self, message: str) -> str | None
```

CLI: `planning admin login` prints `PLANNING_TOKEN=<token>` (like the carried `ADMIN_TOKEN=`); `planning admin logout` ends it.

## External integration tests (mocked server + fake prompt)

1. Correct password -> one POST /admin/sessions with that password; returns the token.
2. Wrong password (403) -> asks again; after 3 failures raises LoginFailed.
3. Cancel -> LoginCancelled, no request sent.
4. No display -> NoDisplay, no request sent, no terminal prompt.
5. The password never appears in logs, exceptions or stdout.
