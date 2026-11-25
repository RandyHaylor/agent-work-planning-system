from __future__ import annotations


class ProseWrapper:
    """Soft wrap at a fixed width; never wraps fenced code, tables, headings; keeps list markers' indent."""

    def __init__(self, width: int) -> None:
        self.width = width

    def wrap(self, text: str) -> str:
        raise NotImplementedError("level 7")
