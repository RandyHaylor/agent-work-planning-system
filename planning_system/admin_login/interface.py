"""Public interface of admin_login."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class PasswordPrompt(ABC):
    """The password window (a fake in tests)."""

    @abstractmethod
    def ask(self, message: str) -> Optional[str]:
        """Typed password, or None on cancel. Raises NoDisplay when there is no display."""


class AdminLoginInterface(ABC):

    @abstractmethod
    def login(self) -> str:
        """Admin session token. Raises LoginCancelled / LoginFailed / NoDisplay."""
