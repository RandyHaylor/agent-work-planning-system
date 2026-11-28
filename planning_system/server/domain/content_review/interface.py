"""ReviewLedger: the one public interface of content_review. Owns review records and who holds them;
never writes nodes. Pull model: reviewers take the oldest pending record (never two at once)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Optional

from .types import ReviewPacket, ReviewRecord, Verdict


class ReviewLedger(ABC):
    @abstractmethod
    def open(self, project_id: int, node_id: int, content_reference_id: str, claim_tag: str) -> ReviewRecord:
        """A new pending record for one content item."""

    @abstractmethod
    def open_node(self, project_id: int, node_id: int) -> ReviewRecord:
        """A new pending whole-node review (guess screen, build log #60 (5)); the node's earlier not-yet-decided
        or failed node reviews become superseded (the node changed since)."""

    @abstractmethod
    def supersede_for(self, content_reference_id: str) -> None:
        """Every not-yet-superseded record of that content item -> superseded (on replace_content)."""

    @abstractmethod
    def get(self, review_id: str) -> ReviewRecord:
        """NotFound when unknown."""

    @abstractmethod
    def list(self, project_id: int, status: Optional[str] = None,
             node_id: Optional[int] = None) -> list[ReviewRecord]:
        """Oldest first."""

    @abstractmethod
    def blocking_for_node(self, node_id: int) -> list[ReviewRecord]:
        """The node's pending, taken or failed records (a node can't be set done while any exist)."""

    @abstractmethod
    def take_next(self, project_id: int, reviewer: str) -> Optional[ReviewPacket]:
        """Expires old leases, then takes the oldest pending record (SKIP LOCKED); None when empty."""

    @abstractmethod
    def submit(self, review_id: str, reviewer: str, verdict: Verdict) -> ReviewRecord:
        """Only the holder of a taken record; Conflict otherwise."""

    @abstractmethod
    def release(self, review_id: str, reviewer: str) -> None:
        """Back to pending; only the holder (Conflict otherwise)."""

    @abstractmethod
    def expire_leases(self, older_than: timedelta) -> int:
        """Taken longer than older_than -> pending; returns how many."""
