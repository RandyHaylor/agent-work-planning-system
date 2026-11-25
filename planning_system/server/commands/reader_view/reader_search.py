"""POST /reader/search: fastReader search across the given items.
The id (temp cache id or reference id) is resolved by the Reader's cache adapter."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from ..command import ReadCommand
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderSearch(ReadCommand):
    terms: str
    reader_ids: tuple[str, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return CanReadReaderItems(self.reader_ids)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reader.search(principal, self.terms, self.reader_ids, self.options)
