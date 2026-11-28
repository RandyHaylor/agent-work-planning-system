"""GET /references/search?q=&limit=: stored references matching the words, best first (supersede spec "Search
first": agents search stored references before loading a source or asking the user)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal

from .command import ReadCommand
from .permissions import Authenticated, Permission


@dataclass(frozen=True)
class SearchReferences(ReadCommand):
    query: str
    limit: int = 10

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise Invalid("search needs words (q)")
        if not 1 <= self.limit <= 50:
            raise Invalid("limit must be 1-50")

    def required_permission(self) -> Permission:
        return Authenticated()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.related.search(self.query, self.limit)
