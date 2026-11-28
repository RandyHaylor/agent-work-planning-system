"""Ports content_review needs: ReviewStoragePort (Postgres impl in storage), Clock."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Optional

from .types import ReviewRecord


class ReviewStoragePort(ABC):
    @abstractmethod
    def add(self, record: ReviewRecord) -> None: ...

    @abstractmethod
    def get(self, review_id: str) -> Optional[ReviewRecord]: ...

    @abstractmethod
    def save(self, record: ReviewRecord) -> None:
        """Replaces the record with the same id."""

    @abstractmethod
    def find(self, project_id: Optional[int] = None, statuses: Optional[Iterable[str]] = None,
             node_id: Optional[int] = None, content_reference_id: Optional[str] = None,
             target_kind: Optional[str] = None, candidate_id: Optional[str] = None) -> list[ReviewRecord]:
        """Matching records, oldest (created_at, id) first; None = any."""

    @abstractmethod
    def lock_oldest_pending(self, project_id: int) -> Optional[ReviewRecord]:
        """The oldest pending record of the project, row-locked for this transaction; records locked by
        another transaction are skipped (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)."""

    @abstractmethod
    def taken_before(self, cutoff: datetime) -> list[ReviewRecord]: ...


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
