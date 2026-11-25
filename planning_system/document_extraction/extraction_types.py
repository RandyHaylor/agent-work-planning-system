"""Data types for document_extraction (spec 05-spec-document-extraction.md). Data only."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal, Mapping

TextKind = Literal["prose", "markdown", "json", "jsonl", "plain"]
OriginKind = Literal["web", "upload", "web_search"]


@dataclass(frozen=True)
class SourceDocument:
    """Produced by a source fetcher (05-spec-source-fetching.md)."""
    raw_bytes: bytes
    locator: str
    origin_kind: OriginKind
    fetched_at: datetime
    content_type_header: str | None = None
    file_name: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionInput:
    """What a strategy sees. `decoded_text` is lazy and cached; PDF/docx strategies never call it."""
    raw_bytes: bytes
    content_type: str
    decoded_text: Callable[[], str]
    base_url: str | None = None


@dataclass(frozen=True)
class StrategyOutput:
    text: str
    kind: TextKind


@dataclass(frozen=True)
class AttemptRecord:
    strategy: str
    error: str | None  # None = this one was used


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    strategy_used: str
    content_type: str
    text_sha256: str
    raw_sha256: str
    attempts: tuple[AttemptRecord, ...]
    available_strategies: tuple[str, ...]


class StrategyFailed(Exception):
    """Raised by a strategy: library error, empty output, or input it can't read."""


class ExtractionFailed(Exception):
    """Every strategy tried failed."""

    def __init__(self, attempts: tuple[AttemptRecord, ...]) -> None:
        self.attempts = tuple(attempts)
        super().__init__("; ".join(f"{a.strategy}: {a.error}" for a in self.attempts) or "no strategy ran")


class UnknownStrategy(Exception):
    """`strategy=` names nothing registered."""
