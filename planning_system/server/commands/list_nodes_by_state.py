"""GET /nodes?project_id=&state=: ProjectTree.list_nodes (log #17)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import ReadCommand
from .permissions import CanReadNode, Permission


@dataclass(frozen=True)
class ListNodesByState(ReadCommand):
    project_id: int
    state: Optional[str] = None

    def required_permission(self) -> Permission:
        return CanReadNode(self.project_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.tree.list_nodes(self.project_id, self.state)
