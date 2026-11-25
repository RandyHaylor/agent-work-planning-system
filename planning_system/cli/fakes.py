"""FakeCommandLine: a minimal working `planning` interpreter over command_table (stands in for the real one)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from planning_system.api_client import ApiError
from planning_system.contract import DomainError
from planning_system.local_client.task_runner import TaskStartRequest

from .command_table import COMMANDS
from .interface import CommandLineInterface
from .types import (EXIT_OK, EXIT_SERVER_ERROR, EXIT_USAGE, TARGET_API, TARGET_GUIDANCE_EDITOR, TARGET_HELP,
                    TARGET_LOCAL, TARGET_LOGIN, Arg, CliDependencies, CommandSpec)

_ARG_KWARGS = {
    "str": {}, "int": {"type": int}, "ints": {"type": int, "nargs": "+"}, "strs": {"nargs": "*"},
    "flag": {"action": "store_true"}, "remainder": {"nargs": argparse.REMAINDER},
}


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="planning")
    parser.add_argument("--text", action="store_true", help="readable output instead of JSON")
    groups: dict[tuple, Any] = {(): parser.add_subparsers(dest="word0", required=True)}
    for spec in COMMANDS:
        for depth in range(1, len(spec.words)):
            prefix = spec.words[:depth]
            if prefix not in groups:
                sub = groups[prefix[:-1]].add_parser(prefix[-1])
                groups[prefix] = sub.add_subparsers(dest=f"word{depth}", required=True)
        command_parser = groups[spec.words[:-1]].add_parser(spec.words[-1], help=spec.help)
        command_parser.set_defaults(spec=spec)
        for arg in spec.arguments:
            _add_argument(command_parser, arg)
    return parser


def _add_argument(parser: argparse.ArgumentParser, arg: Arg) -> None:
    kwargs = dict(_ARG_KWARGS[arg.kind], help=arg.help)
    if arg.name.startswith("--"):
        kwargs.update(dest=arg.dest, required=arg.required)
        if arg.kind != "flag":
            kwargs["default"] = arg.default
        parser.add_argument(arg.name, **kwargs)
    else:
        parser.add_argument(arg.dest, metavar=arg.name.upper(), **kwargs)


class FakeCommandLine(CommandLineInterface):

    def __init__(self, dependencies: CliDependencies):
        self._dependencies = dependencies
        self._parser = _build_parser()

    def run(self, argv: Sequence[str], environment: Mapping[str, str], stdout: TextIO, stderr: TextIO) -> int:
        try:
            parsed = self._parser.parse_args(list(argv))
        except _UsageError as error:
            print(f"usage error: {error}", file=stderr)
            return EXIT_USAGE
        except SystemExit as exit_:          # --help
            return EXIT_OK if exit_.code in (0, None) else EXIT_USAGE
        spec: CommandSpec = parsed.spec
        settings = self._dependencies.settings_from_environment(environment)
        if spec.authenticated and not settings.token:
            print("PLANNING_TOKEN is not set", file=stderr)
            return EXIT_USAGE
        try:
            result = self._dispatch(spec, parsed, settings)
        except (DomainError, ApiError) as error:
            print(f"error: {type(error).__name__}: {error}", file=stderr)
            return EXIT_SERVER_ERROR
        print(json.dumps(result, indent=2, default=_to_json), file=stdout)
        return EXIT_OK

    def _dispatch(self, spec: CommandSpec, parsed: argparse.Namespace, settings) -> Any:
        arguments = {**spec.fixed, **{arg.dest: getattr(parsed, arg.dest) for arg in spec.arguments}}
        api = self._dependencies.api_factory(settings)
        if spec.mapper:
            arguments = _MAPPERS[spec.mapper](arguments, api)
        targets = {
            TARGET_API: lambda: getattr(api, spec.method)(**arguments),
            TARGET_LOCAL: lambda: getattr(self._dependencies.local_client_factory(settings), spec.method)(**arguments),
            TARGET_LOGIN: lambda: f"PLANNING_TOKEN={self._dependencies.admin_login_factory(api).login()}",
            TARGET_HELP: lambda: self._parser.format_help(),
            TARGET_GUIDANCE_EDITOR: lambda: self._dependencies.launch_guidance_editor(),
        }
        return targets[spec.target]()


def _to_json(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else str(value)


def _drop_unset(arguments: dict, api) -> dict:
    return {key: value for key, value in arguments.items() if value is not None}


def _text_or_file(arguments: dict, api) -> dict:
    file_name = arguments.pop("file")
    text = arguments.pop("text")
    return {**_drop_unset(arguments, api), "text": text if text is not None else Path(file_name).read_text()}


def _own_task(arguments: dict, api) -> dict:
    return {"node_id": api.me()["scope_node_id"], **arguments}


def _task_start_request(arguments: dict, api) -> dict:
    return {"request": TaskStartRequest(arguments["node_id"], arguments["agent_id"], arguments["role"] or "worker",
                                        arguments["token"], Path(arguments["working_directory"]))}


def _load_source(arguments: dict, api) -> dict:
    source = (arguments.pop("source") or [None])[0]
    location = {} if source is None else (
        {"url": source} if source.startswith(("http://", "https://")) else {"file_path": Path(source)})
    return {**_drop_unset(arguments, api), **location}


_MAPPERS = {"drop_unset": _drop_unset, "text_or_file": _text_or_file, "own_task": _own_task,
            "task_start_request": _task_start_request, "load_source": _load_source}
