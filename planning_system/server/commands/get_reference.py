"""GET /references/{id}: the reference, always its newest version. A superseded id returns the superseding
reference with `requested_id` and a `superseded_note` (user 2026-11-27: "Reads of superseded references obviously
must return the superseding information as well as a note that it was superceded")."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import ReadCommand
from .permissions import CanReadReference, Permission


def superseded_note(requested_id: str, current_id: str) -> str:
    return f"{requested_id} was superseded; this is the current version {current_id}"


@dataclass(frozen=True)
class GetReference(ReadCommand):
    reference_id: str

    def required_permission(self) -> Permission:
        return CanReadReference(self.reference_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        current = services.references.get(self.reference_id, follow_superseded=True)
        result = dataclasses.asdict(current)
        if current.id != self.reference_id:
            result.update(requested_id=self.reference_id,
                          superseded_note=superseded_note(self.reference_id, current.id))
        return result
