"""POST /reader/cite: TempCache.cite (temp cache -> references, keeps the id)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class CiteCacheItem(WriteCommand):
    reader_id: str
    start_line: int
    end_line: int

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reader.cite(principal, self.reader_id, self.start_line, self.end_line)
