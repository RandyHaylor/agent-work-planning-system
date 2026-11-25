"""commands: the `bootstrap` and `set-admin-password` command bodies, built from the storage config
section (the server composition delegates to these)."""
from __future__ import annotations

import sys

from planning_system.configuration import ConfigSection
from planning_system.contract import DomainError

from .admin_password_setup import PasswordHashSetup
from .database_creation import PostgresDatabaseSetup
from .first_time_setup import Bootstrapper
from .password_prompt import TerminalPasswordPrompt


def build_bootstrapper(storage_section: ConfigSection) -> Bootstrapper:
    from planning_system.server.storage import create_storage
    return Bootstrapper(create_storage(storage_section), PostgresDatabaseSetup(storage_section),
                        PasswordHashSetup(), TerminalPasswordPrompt())


def bootstrap_command(storage_section: ConfigSection) -> int:
    return _run(lambda: build_bootstrapper(storage_section).bootstrap())


def set_admin_password_command(storage_section: ConfigSection) -> int:
    return _run(lambda: build_bootstrapper(storage_section).set_admin_password())


def _run(step) -> int:
    try:
        result = step()
    except DomainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for message in result.messages:
        print(message)
    return 0
