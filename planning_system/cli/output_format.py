"""output_format: prints the server's JSON as-is (default) or readable text for toc/get/search (`--text`).

Level 6 scaffold: hollow.
"""
from __future__ import annotations

from typing import Any, TextIO


def print_result(result: Any, stream: TextIO, as_text: bool = False) -> None:
    raise NotImplementedError("level 7")
