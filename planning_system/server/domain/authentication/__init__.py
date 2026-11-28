"""authentication: credential -> Principal (spec: planning/05-spec-authentication.md).

Public surface: import from this package, not its files. `fakes` stays a separate
test-support submodule."""
from .admin_session import AdminSessionService
from .credential_authenticator import CredentialAuthenticatorService
from .credential_issuer import CredentialIssuerService
from .interface import AdminSessions, CredentialAuthenticator, CredentialIssuer
from .password_hashing import PasswordHasher
from .ports import Clock, CredentialStoragePort
from .types import (AgentId, CredentialId, IssuedCredential, KIND_ADMIN_SESSION, KIND_AGENT, KIND_QUOTE_KEY,
    StoredCredential)

__all__ = ["AdminSessionService", "AdminSessions", "AgentId", "Clock", "CredentialAuthenticator",
           "CredentialAuthenticatorService", "CredentialId", "CredentialIssuer", "CredentialIssuerService",
           "CredentialStoragePort", "IssuedCredential", "KIND_ADMIN_SESSION", "KIND_AGENT", "KIND_QUOTE_KEY",
           "PasswordHasher", "StoredCredential"]
