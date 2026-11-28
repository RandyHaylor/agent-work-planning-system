"""POST /nodes/{id}/supplementary: ProjectTree.insert_before(node_id, title, labels={kind label},
context_summary). kind: tech_spike | requirement_request."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal
from planning_system.server.domain.project_tree import REQUIREMENT_REQUEST, TECH_SPIKE

from .command import WriteCommand
from .permissions import CanCreateSupplementaryTask, Permission

KIND_LABELS = {"tech_spike": TECH_SPIKE, "requirement_request": REQUIREMENT_REQUEST}
SUPPLEMENTARY_KINDS = frozenset(KIND_LABELS)


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
        services.enforcement.check_title(self.title)
        return services.tree.insert_before(self.node_id, self.title, (KIND_LABELS[self.kind],),
                                           self.context_summary)
