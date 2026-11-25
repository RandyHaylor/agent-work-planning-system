"""GET /reader/{id}/get: fastReader get (query params passed through).
The id (temp cache id or reference id) is resolved by the Reader's cache adapter."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from ..command import ReadCommand
from ..permissions import CanReadReaderItems, Permission


@dataclass(frozen=True)
class ReaderGet(ReadCommand):
    reader_id: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reader.get(principal, self.reader_id, self.params)
