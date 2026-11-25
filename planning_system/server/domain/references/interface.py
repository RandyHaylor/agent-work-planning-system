"""Public interfaces of references: the permanent ReferenceLibrary and the per-agent TempCache.

Reading the cache (load, toc, get, search, json) belongs to the copied-in reader (fastReader), not here.
"""
from abc import ABC, abstractmethod
from typing import Mapping, Optional

from .types import AgentId, CacheId, Citation, NodeId, Reference, ReferenceId, TempCacheEntry


class ReferenceLibrary(ABC):
    @abstractmethod
    def get(self, ref_id: ReferenceId, follow_superseded: bool = True) -> Reference: ...

    @abstractmethod
    def read_lines(self, ref_id: ReferenceId, start: int, end: int) -> str:
        """Lines start..end (1-based, inclusive) of that fixed item."""

    @abstractmethod
    def store_user_exchange(self, session_id: str, user_message: str, pre_text: str) -> Reference:
        """Same content returns the same reference."""

    @abstractmethod
    def store_proposal_response(self, node_id: NodeId, text: str) -> Reference: ...

    @abstractmethod
    def store_node_text(self, text: str, node_id: NodeId,
                        replaces: Optional[ReferenceId] = None) -> Reference:
        """With replaces: the old reference is superseded by the new one."""

    @abstractmethod
    def render(self, citation: Citation) -> str:
        """Server-rendered quoted text of the cited lines; raises Invalid for a bad pointer."""

    @abstractmethod
    def supersede(self, old_id: ReferenceId, new_id: ReferenceId) -> None: ...


class TempCache(ABC):
    """temp_cache_lifecycle: per-agent temp cache; cite moves an item into references; TTL purge."""

    @abstractmethod
    def put(self, owner: AgentId, text: str, metadata: Mapping[str, str]) -> TempCacheEntry: ...

    @abstractmethod
    def get(self, cache_id: CacheId) -> TempCacheEntry: ...

    @abstractmethod
    def cite(self, cache_id: CacheId, start_line: int, end_line: int) -> Citation:
        """Moves the item into references keeping its id (or the existing id for identical content)."""

    @abstractmethod
    def purge_expired(self) -> int:
        """Removes entries older than the TTL; returns how many."""
