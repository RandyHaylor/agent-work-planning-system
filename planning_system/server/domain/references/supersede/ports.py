"""SupersedeCandidateStoragePort (Postgres impl in storage)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .types import SupersedeCandidate


class SupersedeCandidateStoragePort(ABC):
    @abstractmethod
    def add(self, candidate: SupersedeCandidate) -> None: ...

    @abstractmethod
    def get(self, candidate_id: str) -> Optional[SupersedeCandidate]: ...

    @abstractmethod
    def save(self, candidate: SupersedeCandidate) -> None:
        """Replaces the record with the same id."""

    @abstractmethod
    def find(self, project_id: Optional[int] = None, status: Optional[str] = None,
             old_reference_id: Optional[str] = None,
             new_reference_id: Optional[str] = None) -> list[SupersedeCandidate]:
        """Matching records, oldest (created_at, id) first; None = any."""
