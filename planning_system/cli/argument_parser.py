"""argument_parser: builds the argparse (stdlib) tree from command_table. Parse errors raise UsageError."""
from __future__ import annotations

import argparse
from typing import Any

from .command_table import COMMANDS
from .types import Arg

_ARG_KWARGS = {
    "str": {}, "int": {"type": int}, "float": {"type": float}, "ints": {"type": int, "nargs": "+"}, "strs": {"nargs": "*"},
    "flag": {"action": "store_true"}, "remainder": {"nargs": argparse.REMAINDER},
}


class UsageError(Exception):
    """Bad command line (exit 2)."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="planning", description="Thin client for the planning server; prints its JSON.")
    parser.add_argument("--text", dest="text_output", action="store_true", help="readable output instead of JSON")
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
