"""credential_issuer: mint, rotate, revoke (cascade); per-install quote key. Rules via access."""
from .agent_session_keys import AgentSessionKeys
from .interface import CredentialIssuer
from .token_hashing import TokenHasher


class CredentialIssuerService(CredentialIssuer):
    def __init__(self, storage, policy, keys: AgentSessionKeys | None = None,
                 hasher: TokenHasher | None = None):
        self._storage = storage
        self._policy = policy
        self._keys = keys or AgentSessionKeys()
        self._hasher = hasher or TokenHasher()

    def mint(self, issuer, role, project_id, scope_node_id, agent_id):
        raise NotImplementedError

    def mint_quote_key(self, issuer, install_label):
        raise NotImplementedError

    def rotate(self, issuer, credential_id):
        raise NotImplementedError

    def revoke(self, issuer, credential_id):
        raise NotImplementedError
