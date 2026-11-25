"""POST /reader/{id}/json: quick-json-reader with the given flags.
Resolves the id through ReadableTextResolver (temp cache id or reference id), then one view."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from..command import ReadCommand, hollow
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderJson(ReadCommand):
    reader_id: str
    flags: tuple[str, ...] = ()

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
