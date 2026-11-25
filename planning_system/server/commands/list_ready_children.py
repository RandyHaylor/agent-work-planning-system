"""GET /nodes/{id}/ready-children: ProjectTree.ready_siblings(node_id)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import ReadCommand, hollow
from .permissions import CanReadNode, Permission


@dataclass(frozen=True)
class ListReadyChildren(ReadCommand):
    node_id: int

    def required_permission(self) -> Permission:
        return CanReadNode(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
