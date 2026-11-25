"""config_file_reader: reads every config/*.json in the injected folder into one tree of sections.

Each file holds top-level keys (sections); the same key in two files is an error.
"""
from __future__ import annotations

import json
from pathlib import Path

from planning_system.contract import Invalid


def read_config_folder(folder: Path) -> dict:
    folder = Path(folder)
    if not folder.is_dir():
        raise Invalid(f"config folder {folder} does not exist")
    tree: dict = {}
    owner: dict[str, str] = {}
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise Invalid(f"{path}: not valid JSON ({error})") from error
        if not isinstance(data, dict):
            raise Invalid(f"{path}: top level must be an object of sections")
        for key, value in data.items():
            if key in tree:
                raise Invalid(f"config key {key!r} is in both {owner[key]} and {path.name}")
            tree[key], owner[key] = value, path.name
    return tree
