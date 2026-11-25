"""GET /reader/{id}/lines: numbered lines of the item.
The id (temp cache id or reference id) is resolved by the Reader's cache adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from ..command import ReadCommand
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderLines(ReadCommand):
    reader_id: str
    start: Optional[int] = None
    end: Optional[int] = None

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reader.lines(principal, self.reader_id, self.start, self.end)
