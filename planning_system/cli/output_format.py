"""output_format: prints the server's JSON as-is (default) or readable text (`--text`)."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, TextIO


def _to_json(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else str(value)


def _as_text(result: Any) -> str:
    """Strings print as-is; a dict/list prints as indented YAML-ish lines (keys and values, no quoting)."""
    if isinstance(result, str):
        return result
    lines: list[str] = []

    def walk(value: Any, indent: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    lines.append(f"{indent}{key}:")
                    walk(item, indent + "  ")
                else:
                    lines.append(f"{indent}{key}: {item}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(f"{indent}-")
                    walk(item, indent + "  ")
                else:
                    lines.append(f"{indent}- {item}")
        else:
            lines.append(f"{indent}{value}")

    walk(json.loads(json.dumps(result, default=_to_json)), "")
    return "\n".join(lines)


def print_result(result: Any, stream: TextIO, as_text: bool = False) -> None:
    if as_text:
        print(_as_text(result), file=stream)
    else:
        print(json.dumps(result, indent=2, default=_to_json), file=stream)
