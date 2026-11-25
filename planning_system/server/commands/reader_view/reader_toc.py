"""GET /reader/{id}/toc: fastReader toc of the item.
The id (temp cache id or reference id) is resolved by the Reader's cache adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from ..command import ReadCommand
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderToc(ReadCommand):
    reader_id: str

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reader.toc(principal, self.reader_id)
