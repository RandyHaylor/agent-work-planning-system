"""GET /reader/{id}/get: fastReader get (query params passed through).
Resolves the id through ReadableTextResolver (temp cache id or reference id), then one view."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from..command import ReadCommand, hollow
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderGet(ReadCommand):
    reader_id: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
