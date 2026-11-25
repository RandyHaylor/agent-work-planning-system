from __future__ import annotations


def normalize_line_endings(text: str) -> str:
    """CRLF/CR -> LF, strip trailing spaces, drop NULs, single trailing newline."""
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n") + "\n"
