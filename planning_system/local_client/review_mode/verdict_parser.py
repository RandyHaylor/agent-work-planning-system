"""Private: strict JSON answers (the verdict, and each review turn's answer); falls back to SoT's balanced-brace scan from the end of the answer
(requirements_modification_reviewer._iter_balanced_brace_object_substrings_from_end, carried)."""
from __future__ import annotations

import json
from typing import Callable, Iterator, Optional

from .types import UnparseableVerdict, Verdict


def find_json_object(answer: str, accept: Callable[[dict], bool]) -> Optional[dict]:
    """The whole answer as a JSON object, else the last balanced {...} in it, that `accept` approves."""
    for candidate in _candidates(answer):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and accept(data):
            return data
    return None


def parse_verdict(answer: str) -> Verdict:
    data = find_json_object(answer, _is_verdict)
    if data is None:
        raise UnparseableVerdict(f"no JSON verdict in reviewer answer: {answer[:300]!r}")
    title = data.get("suggested_title")
    return Verdict(data["passed"], data["reason"].strip(), title.strip() if isinstance(title, str) and title.strip()
                   else None)


def _is_verdict(data: dict) -> bool:
    return isinstance(data.get("passed"), bool) and isinstance(data.get("reason"), str)


def _candidates(answer: str) -> Iterator[str]:
    yield answer.strip()
    yield from _balanced_brace_objects_from_end(answer)


def _balanced_brace_objects_from_end(text: str) -> Iterator[str]:
    """For each '}' (last to first), walk left tracking depth and yield the substring from the matching '{'.
    Skips braces inside JSON strings (handles escaped quotes)."""
    closing_positions = [i for i, ch in enumerate(text) if ch == "}"]
    for closing in reversed(closing_positions):
        depth = 0
        in_string = False
        for index in range(closing, -1, -1):
            char = text[index]
            if char == '"':
                backslashes = 0
                back = index - 1
                while back >= 0 and text[back] == "\\":
                    backslashes += 1
                    back -= 1
                if backslashes % 2 == 0:
                    in_string = not in_string
            if in_string:
                continue
            if char == "}":
                depth += 1
            elif char == "{":
                depth -= 1
                if depth == 0:
                    yield text[index:closing + 1]
                    break
