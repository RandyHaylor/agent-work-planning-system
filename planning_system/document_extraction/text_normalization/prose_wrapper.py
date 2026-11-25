from __future__ import annotations

import re
import textwrap

_FENCE = re.compile(r"^\s*(```|~~~)")
_UNWRAPPED = re.compile(r"^\s*(#|\|)")
_LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")


class ProseWrapper:
    """Soft wrap at a fixed width; never wraps fenced code, tables, headings; keeps list markers' indent."""

    def __init__(self, width: int) -> None:
        self.width = width

    def wrap(self, text: str) -> str:
        lines: list[str] = []
        in_fence = False
        trailing_newline = text.endswith("\n")
        for line in text.split("\n") if not trailing_newline else text[:-1].split("\n"):
            if _FENCE.match(line):
                in_fence = not in_fence
                lines.append(line)
            elif in_fence or _UNWRAPPED.match(line) or len(line) <= self.width:
                lines.append(line)
            else:
                lines.extend(self._wrap_line(line))
        return "\n".join(lines) + ("\n" if trailing_newline else "")

    def _wrap_line(self, line: str) -> list[str]:
        marker = _LIST_MARKER.match(line)
        indent = " " * (len(marker.group(0)) if marker else len(line) - len(line.lstrip()))
        return textwrap.wrap(line, self.width, subsequent_indent=indent, break_long_words=False,
                             break_on_hyphens=False) or [line]
