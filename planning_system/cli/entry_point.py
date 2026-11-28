"""entry_point: the `planning` script. argparse (stdlib) subcommands built from command_table; each handler =
parse args -> one api_client / local_client call -> print JSON. No business logic.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Mapping, Optional, Sequence, TextIO

from planning_system.api_client import ApiError
from planning_system.errors import DomainError

from .argument_mappers import MAPPERS
from .argument_parser import UsageError, build_parser
from .interface import CommandLineInterface
from .output_format import print_result
from .types import (EXIT_OK, EXIT_SERVER_ERROR, EXIT_USAGE, TARGET_API, TARGET_GUIDANCE_EDITOR, TARGET_HELP,
                    TARGET_LOCAL, TARGET_LOGIN, CliDependencies, CommandSpec)


class PlanningCommandLine(CommandLineInterface):

    def __init__(self, dependencies: CliDependencies):
        self._dependencies = dependencies
        self._parser = build_parser()

    def run(self, argv: Sequence[str], environment: Mapping[str, str], stdout: TextIO, stderr: TextIO) -> int:
        try:
            parsed = self._parser.parse_args(list(argv))
        except UsageError as error:
            print(f"usage error: {error}", file=stderr)
            return EXIT_USAGE
        except SystemExit as exit_:          # --help
            return EXIT_OK if exit_.code in (0, None) else EXIT_USAGE
        spec: CommandSpec = parsed.spec
        settings = self._dependencies.settings_from_environment(environment)
        if spec.authenticated and not settings.token:
            print("PLANNING_TOKEN is not set (run `planning admin login` or use your agent token)", file=stderr)
            return EXIT_USAGE
        try:
            result = self._dispatch(spec, parsed, settings)
        except (DomainError, ApiError) as error:
            print(f"error: {type(error).__name__}: {error}", file=stderr)
            return EXIT_SERVER_ERROR
        print_result(result, stdout, as_text=parsed.text_output)
        return EXIT_OK

    def _dispatch(self, spec: CommandSpec, parsed: argparse.Namespace, settings) -> Any:
        arguments = {**spec.fixed, **{arg.dest: getattr(parsed, arg.dest) for arg in spec.arguments}}
        api = self._dependencies.api_factory(settings)
        if spec.mapper:
            arguments = MAPPERS[spec.mapper](arguments, api)
        targets = {
            TARGET_API: lambda: getattr(api, spec.method)(**arguments),
            TARGET_LOCAL: lambda: getattr(self._dependencies.local_client_factory(settings), spec.method)(**arguments),
            TARGET_LOGIN: lambda: f"PLANNING_TOKEN={self._dependencies.admin_login_factory(api).login()}",
            TARGET_HELP: lambda: self._parser.format_help(),
            TARGET_GUIDANCE_EDITOR: lambda: self._dependencies.launch_guidance_editor(),
        }
        result = targets[spec.target]()
        if spec.after:
            self._after_steps()[spec.after](result)
        return result

    def _after_steps(self) -> dict:
        return {"store_quote_key": lambda result: self._dependencies.store_quote_key(result["token"])
                if isinstance(result, dict) and "token" in result else None}


def _launch_guidance_editor() -> None:
    """Starts prompt_builder's website on the local preset folder and blocks until Ctrl-C."""
    import threading

    from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import resolve_user_rule_builder_folder
    from planning_system.prompt_builder.guidance_editor import GuidanceEditor

    editor = GuidanceEditor(resolve_user_rule_builder_folder())
    session = editor.launch()
    print(f"guidance editor: {session.url} (presets saved to {session.store_folder}); Ctrl-C to stop",
          file=sys.stderr)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        editor.shutdown()


def default_dependencies() -> CliDependencies:
    from planning_system.admin_login import AdminLoginFlow, TkPasswordPromptWindow
    from planning_system.api_client import PlanningApiClient
    from planning_system.api_client.client_settings import settings_from_environment
    from planning_system.local_client import build_local_client
    from planning_system.local_client.client_credentials import FileClientCredentials
    from planning_system.local_client.client_paths import ClientPaths

    def store_quote_key(token: str) -> None:
        FileClientCredentials(ClientPaths.from_environment().home).write_quote_key(token)

    return CliDependencies(
        store_quote_key=store_quote_key,
        api_factory=PlanningApiClient,
        local_client_factory=build_local_client,
        admin_login_factory=lambda api: AdminLoginFlow(api, TkPasswordPromptWindow()),
        settings_from_environment=settings_from_environment,
        launch_guidance_editor=_launch_guidance_editor,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    command_line = PlanningCommandLine(default_dependencies())
    return command_line.run(sys.argv[1:] if argv is None else argv, os.environ, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
