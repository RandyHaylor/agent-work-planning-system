"""Data types (data only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

TextKind = Literal["json", "jsonl"]
OutputFormat = Literal["txt", "csv", "json"]


@dataclass(frozen=True)
class NodeRunResult:
    stdout: str
    stderr: str
    exit_code: int


@dataclass(frozen=True)
class LineRange:
    start_line: int  # 1-based, in the stored text
    end_line: int


@dataclass(frozen=True)
class JsonReaderOutput:
    text: str  # rendered output, each addressed line annotated "(ln S-E)"
    line_ranges: Mapping[str, LineRange] = field(default_factory=dict)  # absolute address "0-3-1" -> range
    output_format: OutputFormat = "txt"


class JsonReaderUsageError(Exception):
    """quick-json-reader exit 2 (bad flags)."""


class JsonReaderInputError(Exception):
    """quick-json-reader exit 1 (not JSON/JSONL)."""


class NodeRunTimeout(Exception):
    """The node process exceeded its timeout."""
