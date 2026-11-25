"""issuing: create a credential, store its digest only, hand back the plaintext once (private helper)."""
from dataclasses import replace

from .agent_session_keys import AgentSessionKeys
from .token_hashing import TokenHasher
from .types import IssuedCredential, StoredCredential


class TokenIssuing:
    def __init__(self, storage, keys: AgentSessionKeys, hasher: TokenHasher):
        self._storage = storage
        self._keys = keys
        self._hasher = hasher

    def issue(self, principal, kind, minted_by=None, label=None, expires_at=None) -> IssuedCredential:
        token = self._keys.new_key()
        stored = StoredCredential(self._keys.new_credential_id(), self._hasher.digest(token),
                                  principal, kind, minted_by, label, False, expires_at)
        self._storage.save(stored)
        return IssuedCredential(token, stored.credential_id, principal)

    def reissue(self, stored: StoredCredential) -> IssuedCredential:
        """Same credential, new token; the old token stops working."""
        token = self._keys.new_key()
        self._storage.save(replace(stored, token_digest=self._hasher.digest(token)))
        return IssuedCredential(token, stored.credential_id, stored.principal)
