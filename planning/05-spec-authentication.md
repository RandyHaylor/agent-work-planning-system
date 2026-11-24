# Spec: authentication

APPROVED by the user, 2026-11-23, in Slack: "approve authentication (with 1b)". No global server access token; per-principal credentials over TLS; a locally self-signed certificate for v1.

From recorded decisions only: keep the carried PBKDF2 password hashing (600,000 iterations) and SHA-256 token digests; agent session keys persist so agents can resume; admin sessions are temporary, started by a popup where the human types a password only they know, after which an agent can act as admin ("keeping agents honest, not high security"); mint, rotate and revoke with cascade (carried); a per-install quote key that can only submit user quotes; authentication maps a credential to an agent ID in agent_registry; storage through a port.

```python
@dataclass(frozen=True)
class IssuedCredential:
    token: str                       # plaintext, shown once at mint/rotate
    credential_id: CredentialId
    principal: Principal

class CredentialAuthenticator:
    def authenticate(self, presented_token) -> Principal            # raises if unknown, revoked or expired

class CredentialIssuer:
    def mint(self, issuer: Principal, role, project_id, scope_node_id, agent_id) -> IssuedCredential
    def mint_quote_key(self, issuer: Principal, install_label) -> IssuedCredential   # admin only
    def rotate(self, issuer: Principal, credential_id) -> IssuedCredential
    def revoke(self, issuer: Principal, credential_id) -> None       # cascades to credentials minted beneath

class AdminSessions:
    def start(self, password) -> IssuedCredential   # called by the admin_login popup; temporary session
    def end(self, session_id) -> None
```

Rules checked through `access` (can_mint, can_revoke, can_rotate). Stored as digests only; plaintext never stored.

## External integration tests (mocked credential storage)

1. A minted token authenticates to the right Principal and agent ID; a wrong token fails.
2. Only the digest is stored; the plaintext can't be read back from storage.
3. Revoking a planner credential also revokes the worker credentials it minted.
4. A rotated credential's old token stops working; the new one works.
5. An agent session key keeps working across restarts (persistent).
6. An admin session starts only with the right password and stops working when it ends or expires.
7. A quote key authenticates as quote_client and nothing else.

## Answered

1. Today's server-wide access token (`X-Server-Access`) is dropped (user chose b).
