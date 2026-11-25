"""GET /references/{id}/lines: ReferenceLibrary.read_lines (whole item when no range)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import ReadCommand, hollow
from .permissions import CanReadReference, Permission


@dataclass(frozen=True)
class ReadReferenceLines(ReadCommand):
    reference_id: str
    start: Optional[int] = None
    end: Optional[int] = None

    def required_permission(self) -> Permission:
        return CanReadReference(self.reference_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
