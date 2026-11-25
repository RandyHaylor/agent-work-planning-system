from __future__ import annotations

import json


def format_json(text: str, indent: int) -> str:
    """Pretty-print with a fixed indent, key order kept."""
    return json.dumps(json.loads(text), indent=indent, ensure_ascii=False) + "\n"
