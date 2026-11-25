"""credential_authenticator: presented token -> Principal."""
from dataclasses import replace

from planning_system.contract import Forbidden

from .interface import CredentialAuthenticator
from .token_hashing import TokenHasher


class CredentialAuthenticatorService(CredentialAuthenticator):
    def __init__(self, storage, clock, hasher: TokenHasher | None = None):
        self._storage = storage
        self._clock = clock
        self._hasher = hasher or TokenHasher()

    def authenticate(self, presented_token):
        stored = self._storage.find_by_digest(self._hasher.digest(presented_token))
        if stored is None or stored.revoked:
            raise Forbidden("unknown or revoked credential")
        if stored.expires_at is not None and self._clock.now() >= stored.expires_at:
            raise Forbidden("expired credential")
        return replace(stored.principal, credential_id=stored.credential_id)
