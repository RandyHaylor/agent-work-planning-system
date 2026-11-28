"""line_range_mapping: where a cited line range of an old version sits in the version that superseded it.
Uses difflib's line matching (the standard diff algorithm, as in `diff`), not a custom one."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MappedRange:
    start: Optional[int]        # 1-based inclusive in the new text; None when every cited line was deleted
    end: Optional[int]
    unchanged: bool             # the new range's text equals the old range's text


def map_line_range(old_text: str, new_text: str, start: int, end: int) -> MappedRange:
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    mapped: list[int] = []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        overlap = range(max(a0, start - 1), min(a1, end))
        if not overlap or tag == "insert":
            continue
        if tag == "equal":
            mapped.extend(b0 + (i - a0) for i in overlap)
        elif tag == "replace":
            mapped.extend(range(b0, b1))
    if not mapped:
        return MappedRange(None, None, False)
    new_start, new_end = min(mapped) + 1, max(mapped) + 1
    unchanged = old_lines[start - 1:end] == new_lines[new_start - 1:new_end]
    return MappedRange(new_start, new_end, unchanged)
