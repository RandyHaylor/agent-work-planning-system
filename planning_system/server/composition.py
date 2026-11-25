"""The server's own composition root (not main): from its config section it builds storage, domain
services, CommandRunner, FastAPI app and bootstrap, and offers the commands `run`, `bootstrap` and
`set-admin-password`. Named in config/server.json as the server component's factory."""
from __future__ import annotations

from typing import Callable

from planning_system.configuration import ConfigSection


class ServerComponent:
    def __init__(self, section: ConfigSection):
        self._section = section

    def commands(self) -> dict[str, Callable[[list[str]], int]]:
        return {"run": self.run, "bootstrap": self.bootstrap,
                "set-admin-password": self.set_admin_password}

    def run(self, args: list[str]) -> int:
        """purge expired temp cache (log #17) -> create_storage -> DomainServicesFactory ->
        CommandRunner -> create_app (with guidance_service override) -> serve."""
        raise NotImplementedError("level 7")

    def bootstrap(self, args: list[str]) -> int:
        """Bootstrapper(storage, PostgresDatabaseSetup, PasswordHashSetup, TerminalPasswordPrompt)."""
        from planning_system.server.bootstrap.commands import bootstrap_command
        return bootstrap_command(self._section.child("storage"))

    def set_admin_password(self, args: list[str]) -> int:
        from planning_system.server.bootstrap.commands import set_admin_password_command
        return set_admin_password_command(self._section.child("storage"))


def create_server(section: ConfigSection) -> ServerComponent:
    return ServerComponent(section)
