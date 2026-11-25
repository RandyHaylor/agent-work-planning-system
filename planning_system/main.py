"""Entry point `planning-server [--config DIR] <command> [args...]`.

Steps only: load configuration, load the components it names, run the chosen command. Knows nothing
concrete (no server, web framework or database); every concrete choice comes from config.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from planning_system.configuration import Configuration, load_component, load_configuration

DEFAULT_CONFIG_DIR = "config"
CONFIG_ENV = "PLANNING_CONFIG_DIR"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    folder, args = split_config_folder(args)
    configuration = load_configuration(folder)
    components = load_components(configuration)
    command = find_command(components, args[:1])
    if command is None:
        return report_unknown_command(components, args[:1])
    return command(args[1:])


def split_config_folder(args: list[str]) -> tuple[Path, list[str]]:
    if len(args) >= 2 and args[0] == "--config":
        return Path(args[1]), args[2:]
    return Path(os.environ.get(CONFIG_ENV, DEFAULT_CONFIG_DIR)), args


def load_components(configuration: Configuration) -> list:
    names = configuration.top().get("components")
    return [load_component(configuration.section(name)) for name in names]


def available_commands(components: list) -> dict[str, Callable[[list[str]], int]]:
    commands: dict = {}
    for component in components:
        commands.update(component.commands())
    return commands


def find_command(components: list, name: list[str]) -> Optional[Callable[[list[str]], int]]:
    return available_commands(components).get(name[0]) if name else None


def report_unknown_command(components: list, name: list[str]) -> int:
    known = ", ".join(sorted(available_commands(components)))
    given = f"unknown command {name[0]!r}. " if name else ""
    print(f"{given}Commands: {known}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
