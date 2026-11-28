"""first_time_setup: Bootstrapper. Steps, one call each: ensure database, migrate, check done, ask
password, store its hash in one read_write transaction. A second run is a no-op that says so.
No root nodes (log #15), no backup keypair (log #7), no token printed (admin uses POST /admin/sessions)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from planning_system.errors import Invalid

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
        messages = []
        if self._database.ensure_database():
            messages.append("created database")
        self._database.migrate()
        messages.append("migrations applied")
        if self._bootstrapped():
            return BootstrapResult(True, (*messages, "already bootstrapped; nothing changed"))
        self._store(self._prompt.ask())
        return BootstrapResult(False, (*messages, "admin password set"))

    def set_admin_password(self):
        if not self._bootstrapped():
            raise Invalid("not bootstrapped yet: run `planning-server bootstrap` first")
        self._store(self._prompt.ask("New admin password"))
        return BootstrapResult(True, ("admin password replaced",))

    def _bootstrapped(self) -> bool:
        with self._storage.transactions.read_only() as conn:
            return self._authentication.admin_password_set(self._storage.stores_for(conn))

    def _store(self, password: str) -> None:
        with self._storage.transactions.read_write() as conn:
            self._authentication.set_admin_password(self._storage.stores_for(conn), password)
