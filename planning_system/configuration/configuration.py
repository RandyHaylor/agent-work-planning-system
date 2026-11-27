"""Configuration: every config/*.json in one folder, ${NAME}s substituted, handed out by section."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from planning_system.contract import Invalid

from .config_file_reader import read_config_file, read_config_folder
from .environment_substitution import EnvironmentSubstitution, read_dotenv
from .section import ConfigSection


class Configuration:
    def __init__(self, tree: Mapping, folder: Path):
        self._folder = Path(folder)
        self._top = ConfigSection("", tree, str(folder))

    def section(self, name: str) -> ConfigSection:
        if not self._top.has(name):
            raise Invalid(f"config section {name!r} not found in any *.json in {self._folder}")
        return self._top.child(name)

    def top(self) -> ConfigSection:
        """The top level itself (e.g. main.json's "components" list)."""
        return self._top


def load_configuration(folder: Path, environ: Optional[Mapping[str, str]] = None,
                       dotenv_path: Optional[Path] = None) -> Configuration:
    """dotenv_path defaults to `.env` beside the config folder, then inside it."""
    folder = Path(folder)
    if dotenv_path is None:
        candidates = (folder.parent / ".env", folder / ".env")
        dotenv_path = next((c for c in candidates if c.is_file()), None)
    substitution = EnvironmentSubstitution(os.environ if environ is None else environ,
                                           read_dotenv(dotenv_path))
    return Configuration(substitution.apply(read_config_folder(folder)), folder)


def load_config_file(path: Path, environ: Optional[Mapping[str, str]] = None) -> Configuration:
    """One config file on its own (e.g. a client-side override file); ${NAME}s from the environment only."""
    path = Path(path)
    substitution = EnvironmentSubstitution(os.environ if environ is None else environ, {})
    return Configuration(substitution.apply(read_config_file(path)), path)
