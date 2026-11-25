"""POST /reader/search: fastReader search across the given items.
Resolves the id through ReadableTextResolver (temp cache id or reference id), then one view."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from..command import ReadCommand, hollow
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderSearch(ReadCommand):
    terms: str
    reader_ids: tuple[str, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return CanReadReaderItems(self.reader_ids)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
