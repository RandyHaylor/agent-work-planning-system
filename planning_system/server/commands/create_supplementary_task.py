"""POST /nodes/{id}/supplementary: ProjectTree.insert_before(node_id, title, labels={kind label},
context_summary). kind: tech_spike | requirement_request."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal

from.command import WriteCommand, hollow
from .permissions import CanCreateSupplementaryTask, Permission

SUPPLEMENTARY_KINDS = frozenset({"tech_spike", "requirement_request"})


@dataclass(frozen=True)
class CreateSupplementaryTask(WriteCommand):
    node_id: int
    kind: str
    title: str
    context_summary: str

    def __post_init__(self) -> None:
        if self.kind not in SUPPLEMENTARY_KINDS:
            raise Invalid(f"kind must be one of {sorted(SUPPLEMENTARY_KINDS)}")

    def required_permission(self) -> Permission:
        return CanCreateSupplementaryTask(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
