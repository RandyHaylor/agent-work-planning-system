"""Public interface of authentication: credential -> Principal; mint/rotate/revoke; admin sessions."""
from abc import ABC, abstractmethod
from typing import Optional

from planning_system.contract import Principal

from .types import CredentialId, IssuedCredential


class CredentialAuthenticator(ABC):
    @abstractmethod
    def authenticate(self, presented_token: str) -> Principal:
        """Raises Forbidden if unknown, revoked or expired."""


class CredentialIssuer(ABC):
    @abstractmethod
    def mint(self, issuer: Principal, role: str, project_id: Optional[int],
             scope_node_id: Optional[int], agent_id: Optional[str]) -> IssuedCredential: ...

    @abstractmethod
    def mint_quote_key(self, issuer: Principal, install_label: str) -> IssuedCredential:
        """Admin only."""

    @abstractmethod
    def rotate(self, issuer: Principal, credential_id: CredentialId) -> IssuedCredential: ...

    @abstractmethod
    def revoke(self, issuer: Principal, credential_id: CredentialId) -> None:
        """Cascades to credentials minted beneath."""


class AdminSessions(ABC):
    @abstractmethod
    def start(self, password: str) -> IssuedCredential:
        """Called by the admin_login popup; temporary session."""

    @abstractmethod
    def end(self, session_id: CredentialId) -> None: ...
