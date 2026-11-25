from __future__ import annotations

import json


def format_jsonl(text: str) -> str:
    """One compact record per line, blank lines dropped."""
    return "".join(json.dumps(json.loads(line), ensure_ascii=False) + "\n"
                   for line in text.splitlines() if line.strip())
