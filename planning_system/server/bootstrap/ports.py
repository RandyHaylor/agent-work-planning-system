"""Ports bootstrap needs. Each step is one call so tests can mock it."""
from __future__ import annotations

from abc import ABC, abstractmethod


class PasswordPrompt(ABC):
    @abstractmethod
    def ask(self, purpose: str = "Admin password") -> str:
        """A password that passes the policy (asked twice, or taken from the env override)."""


class DatabaseSetup(ABC):
    @abstractmethod
    def ensure_database(self) -> bool:
        """Create the `planning_system` database if missing; True when it was created."""

    @abstractmethod
    def migrate(self) -> None:
        """alembic upgrade head (outside the setup transaction; Alembic manages its own)."""


class AuthenticationSetup(ABC):
    """Admin password through authentication's hashing, stored via the credential store of one
    transaction. (CredentialStoragePort only reads the hash, so this port carries the write.)"""

    @abstractmethod
    def admin_password_set(self, stores) -> bool: ...

    @abstractmethod
    def set_admin_password(self, stores, password: str) -> None: ...
