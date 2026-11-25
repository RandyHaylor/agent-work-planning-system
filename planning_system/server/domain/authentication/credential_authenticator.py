"""credential_authenticator: presented token -> Principal."""
from .interface import CredentialAuthenticator
from .token_hashing import TokenHasher


class CredentialAuthenticatorService(CredentialAuthenticator):
    def __init__(self, storage, clock, hasher: TokenHasher | None = None):
        self._storage = storage
        self._clock = clock
        self._hasher = hasher or TokenHasher()

    def authenticate(self, presented_token):
        raise NotImplementedError
