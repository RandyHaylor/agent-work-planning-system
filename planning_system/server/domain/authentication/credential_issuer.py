"""credential_issuer: mint, rotate, revoke (cascade); per-install quote key. Rules via access."""
from dataclasses import replace

from planning_system.contract import Forbidden, NotFound, Principal
from planning_system.server.domain.access.types import ADMIN, QUOTE_CLIENT, CredentialScope

from .agent_session_keys import AgentSessionKeys
from .interface import CredentialIssuer
from .issuing import TokenIssuing
from .token_hashing import TokenHasher
from .types import KIND_AGENT, KIND_QUOTE_KEY


def _scope_of(stored) -> CredentialScope:
    p = stored.principal
    return CredentialScope(p.role, p.project_id, p.scope_node_id)


class CredentialIssuerService(CredentialIssuer):
    def __init__(self, storage, policy, keys: AgentSessionKeys | None = None,
                 hasher: TokenHasher | None = None):
        self._storage = storage
        self._policy = policy
        self._issuing = TokenIssuing(storage, keys or AgentSessionKeys(), hasher or TokenHasher())

    def mint(self, issuer, role, project_id, scope_node_id, agent_id):
        if not self._policy.can_mint(issuer, CredentialScope(role, project_id, scope_node_id), role):
            raise Forbidden(f"{issuer.role} may not mint a {role} credential here")
        principal = Principal(agent_id, role, project_id, scope_node_id)
        return self._issuing.issue(principal, KIND_AGENT, minted_by=issuer.agent_id)

    def mint_quote_key(self, issuer, install_label):
        if issuer.role != ADMIN:
            raise Forbidden("only admin mints a quote key")
        return self._issuing.issue(Principal(None, QUOTE_CLIENT), KIND_QUOTE_KEY, label=install_label)

    def rotate(self, issuer, credential_id):
        stored = self._require(credential_id)
        if not self._policy.can_rotate(issuer, _scope_of(stored)):
            raise Forbidden("may not rotate this credential")
        return self._issuing.reissue(stored)

    def revoke(self, issuer, credential_id):
        stored = self._require(credential_id)
        if not self._policy.can_revoke(issuer, _scope_of(stored)):
            raise Forbidden("may not revoke this credential")
        self._revoke_with_descendants(stored)

    def credential_scope(self, credential_id):
        return _scope_of(self._require(credential_id))

    def _require(self, credential_id):
        stored = self._storage.get(credential_id)
        if stored is None:
            raise NotFound(f"credential {credential_id}")
        return stored

    def _revoke_with_descendants(self, root):
        pending = [root]
        while pending:
            stored = pending.pop()
            if stored.revoked:
                continue
            self._storage.save(replace(stored, revoked=True))
            pending.extend(self._storage.minted_by(stored.principal.agent_id))
