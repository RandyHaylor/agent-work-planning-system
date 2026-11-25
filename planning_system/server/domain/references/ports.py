"""Ports references needs."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

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


# The source fetcher port (any source the reader loads) is source_fetcher_port.SourceFetcher (build log #30).


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
