"""GET /references/{id}: ReferenceLibrary.get."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import ReadCommand, hollow
from .permissions import CanReadReference, Permission


@dataclass(frozen=True)
class GetReference(ReadCommand):
    reference_id: str
    follow_superseded: bool = False

    def required_permission(self) -> Permission:
        return CanReadReference(self.reference_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
