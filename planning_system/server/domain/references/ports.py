"""Ports references needs."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from .types import CacheId, Reference, ReferenceId, TempCacheEntry


class ReferenceStoragePort(ABC):
    @abstractmethod
    def get(self, ref_id: ReferenceId) -> Optional[Reference]: ...

    @abstractmethod
    def find_by_sha256(self, sha256: str) -> Optional[Reference]: ...

    @abstractmethod
    def save(self, reference: Reference) -> None:
        """Insert, or replace by id (only superseded_by ever changes)."""


class TempCacheStoragePort(ABC):
    @abstractmethod
    def get(self, cache_id: CacheId) -> Optional[TempCacheEntry]: ...

    @abstractmethod
    def save(self, entry: TempCacheEntry) -> None: ...

    @abstractmethod
    def delete(self, cache_id: CacheId) -> None: ...

    @abstractmethod
    def created_before(self, cutoff: datetime) -> list[TempCacheEntry]: ...


@dataclass(frozen=True)
class FetchedSource:
    data: bytes
    metadata: Mapping[str, str] = field(default_factory=dict)   # e.g. url, content-type header


class SourceFetcherPort(ABC):
    """Any source the reader loads (URL, uploaded file, web search), not web-only."""

    @abstractmethod
    def fetch(self, source: str) -> FetchedSource: ...


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
