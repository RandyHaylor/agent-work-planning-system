"""Ports authentication needs (credential_storage_port + a clock)."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .types import AgentId, CredentialId, StoredCredential


class CredentialStoragePort(ABC):
    @abstractmethod
    def save(self, credential: StoredCredential) -> None:
        """Insert or replace by credential_id."""

    @abstractmethod
    def get(self, credential_id: CredentialId) -> Optional[StoredCredential]: ...

    @abstractmethod
    def find_by_digest(self, token_digest: str) -> Optional[StoredCredential]: ...

    @abstractmethod
    def minted_by(self, agent_id: AgentId) -> list[StoredCredential]: ...

    @abstractmethod
    def admin_password_hash(self) -> str:
        """The stored PBKDF2 hash of the admin password (set at bootstrap)."""


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
