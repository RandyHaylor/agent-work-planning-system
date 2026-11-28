"""SupersedeCandidates: the one public interface of supersede (nested child of references). Candidates are
records about a pair of references; confirming one is the only way evidence gets superseded."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .types import SupersedeCandidate


class SupersedeCandidates(ABC):

    @abstractmethod
    def propose(self, project_id: int, old_reference_id: str, new_reference_id: str, found_by: str,
                proposed_by: Optional[str], reason: str = "") -> tuple[SupersedeCandidate, bool]:
        """(candidate, created). The same pair in the project returns the existing record (any status, so a
        rejected pair stays rejected). Invalid: same id, unknown or already superseded old reference, origins
        that don't match (document <-> document/knowledge_base, user quote <-> user quote), node text."""

    @abstractmethod
    def get(self, candidate_id: str) -> SupersedeCandidate:
        """NotFound when unknown."""

    @abstractmethod
    def list(self, project_id: int, status: Optional[str] = None) -> list[SupersedeCandidate]:
        """Oldest first."""

    @abstractmethod
    def mark_trial_reviewed(self, candidate_id: str, request_node_id: Optional[int]) -> SupersedeCandidate:
        """Every trial review is decided; request_node_id is the requirement request asking to confirm it."""

    @abstractmethod
    def confirm(self, candidate_id: str, decided_by: str) -> SupersedeCandidate:
        """Supersedes old by new in the library. Conflict unless proposed or trial_reviewed."""

    @abstractmethod
    def reject(self, candidate_id: str, decided_by: str, reason: str) -> SupersedeCandidate:
        """Keeps the pair as "not a supersede" with the reason. Conflict unless proposed or trial_reviewed."""
