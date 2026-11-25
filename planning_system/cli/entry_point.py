"""entry_point: the `planning` script. argparse (stdlib) subcommands built from command_table; each handler =
parse args -> one api_client / local_client call -> print JSON. No business logic.

Level 6 scaffold: PlanningCommandLine is hollow; main() only wires the real dependencies and runs it.
"""
from __future__ import annotations

import os
import sys
from typing import Mapping, Optional, Sequence, TextIO

from .interface import CommandLineInterface
from .types import CliDependencies


class PlanningCommandLine(CommandLineInterface):

    def __init__(self, dependencies: CliDependencies):
        self._dependencies = dependencies

    def run(self, argv: Sequence[str], environment: Mapping[str, str], stdout: TextIO, stderr: TextIO) -> int:
        raise NotImplementedError("level 7")


def default_dependencies() -> CliDependencies:
    from planning_system.admin_login import AdminLoginFlow, TkPasswordPromptWindow
    from planning_system.api_client import PlanningApiClient
    from planning_system.api_client.client_settings import settings_from_environment
    from planning_system.local_client import build_local_client

    def launch_guidance_editor() -> None:
        raise NotImplementedError("level 7: prompt_builder's local website")

    return CliDependencies(
        api_factory=PlanningApiClient,
        local_client_factory=build_local_client,
        admin_login_factory=lambda api: AdminLoginFlow(api, TkPasswordPromptWindow()),
        settings_from_environment=settings_from_environment,
        launch_guidance_editor=launch_guidance_editor,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    command_line = PlanningCommandLine(default_dependencies())
    return command_line.run(sys.argv[1:] if argv is None else argv, os.environ, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
