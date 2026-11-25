"""The cache port fastReader's commands talk to instead of cache files.

fastReader imports nothing from the server. The server implements this port over its
per-agent temp cache and reference library (server/domain/references/); the local
FileReaderCache keeps the original ~/.fastReader/cache behaviour.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping

from planning_system.fastreader.models import Manifest


@dataclass(frozen=True)
class CachedItem:
    item_id: str                 # temp cache id or reference id (same id space; cite keeps the id)
    source_label: str            # URL, file name or search terms
    text: str
    manifest: Manifest
    metadata: Mapping[str, str] = field(default_factory=dict)  # origin_kind, strategy_used, sha256 ...

    @property
    def lines(self) -> list:
        return self.text.split('\n')


@dataclass(frozen=True)
class ReaderCitation:
    item_id: str
    start_line: int              # 1-based, inclusive
    end_line: int                # 1-based, inclusive


class ReaderCachePort(ABC):
    """Bound to one principal by whoever constructs it."""

    @abstractmethod
    def save(self, text: str, manifest: Manifest, source_label: str,
             metadata: Mapping[str, str]) -> str:
        """Store text + manifest; identical text already visible to the caller returns its id."""

    @abstractmethod
    def get(self, item_id: str) -> CachedItem:
        """The item, or a not-found error (FileNotFoundError locally, contract NotFound on the server)."""

    @abstractmethod
    def cite(self, item_id: str, start_line: int, end_line: int) -> ReaderCitation:
        """Move the item into references keeping its id; on an existing reference just cite it."""
