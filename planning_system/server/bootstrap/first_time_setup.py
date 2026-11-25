"""first_time_setup: Bootstrapper. Steps, one call each: ensure database, migrate, check done, ask
password, store its hash in one read_write transaction. A second run is a no-op that says so.
No root nodes (log #15), no backup keypair (log #7), no token printed (admin uses POST /admin/sessions)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .ports import AuthenticationSetup, DatabaseSetup, PasswordPrompt


@dataclass(frozen=True)
class BootstrapResult:
    already_bootstrapped: bool
    messages: tuple[str, ...]


class BootstrapperInterface(ABC):
    @abstractmethod
    def bootstrap(self) -> BootstrapResult: ...

    @abstractmethod
    def set_admin_password(self) -> BootstrapResult:
        """Requires a prior bootstrap (Invalid otherwise); replaces the hash."""


class Bootstrapper(BootstrapperInterface):
    def __init__(self, storage, database: DatabaseSetup, authentication: AuthenticationSetup,
                 prompt: PasswordPrompt):
        self._storage, self._database = storage, database
        self._authentication, self._prompt = authentication, prompt

    def bootstrap(self):
        raise NotImplementedError("level 7")

    def set_admin_password(self):
        raise NotImplementedError("level 7")
