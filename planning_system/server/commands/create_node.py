"""POST /nodes: ProjectTree.create."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanCreateNode, Permission


@dataclass(frozen=True)
class CreateNode(WriteCommand):
    parent_id: int
    title: str
    level_label: str
    context_summary: str
    labels: tuple[str, ...] = ()
    depends_on: Optional[tuple[int, ...]] = None
    position: Optional[int] = None

    def required_permission(self) -> Permission:
        return CanCreateNode(self.parent_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.tree.create(self.parent_id, self.title, self.level_label, self.context_summary,
                                    self.labels, self.depends_on, self.position)
