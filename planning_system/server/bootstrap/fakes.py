"""Test support: a working Bootstrapper, recording ports, and a scripted prompt."""
from __future__ import annotations

from dataclasses import dataclass, field

from planning_system.errors import Invalid

from .first_time_setup import BootstrapperInterface, BootstrapResult
from .ports import AuthenticationSetup, DatabaseSetup, PasswordPrompt


@dataclass
class RecordingDatabaseSetup(DatabaseSetup):
    calls: list = field(default_factory=list)

    def ensure_database(self):
        self.calls.append("ensure_database")
        return True

    def migrate(self):
        self.calls.append("migrate")


@dataclass
class ScriptedPasswordPrompt(PasswordPrompt):
    password: str = "correct horse battery"
    asked: int = 0

    def ask(self, purpose="Admin password"):
        self.asked += 1
        return self.password


class InMemoryAuthenticationSetup(AuthenticationSetup):
    """Keeps the "hash" on the stores object; fail_on_set simulates a failure while storing."""

    def __init__(self, fail_on_set: bool = False):
        self.fail_on_set = fail_on_set

    def admin_password_set(self, stores):
        return getattr(stores, "_admin_password", None) is not None

    def set_admin_password(self, stores, password):
        if self.fail_on_set:
            raise RuntimeError("storage failed")
        object.__setattr__(stores, "_admin_password", "hash:" + password)


class FakeBootstrapper(BootstrapperInterface):
    def __init__(self, storage, database, authentication, prompt):
        self._storage, self._database = storage, database
        self._authentication, self._prompt = authentication, prompt

    def _done(self) -> bool:
        with self._storage.transactions.read_only() as conn:
            return self._authentication.admin_password_set(self._storage.stores_for(conn))

    def _store(self, password):
        with self._storage.transactions.read_write() as conn:
            self._authentication.set_admin_password(self._storage.stores_for(conn), password)

    def bootstrap(self):
        messages = []
        if self._database.ensure_database():
            messages.append("created database")
        self._database.migrate()
        messages.append("migrations applied")
        if self._done():
            return BootstrapResult(True, tuple(messages) + ("already bootstrapped; nothing changed",))
        self._store(self._prompt.ask())
        return BootstrapResult(False, tuple(messages) + ("admin password set",))

    def set_admin_password(self):
        if not self._done():
            raise Invalid("not bootstrapped yet: run `planning-server bootstrap` first")
        self._store(self._prompt.ask("New admin password"))
        return BootstrapResult(True, ("admin password replaced",))
