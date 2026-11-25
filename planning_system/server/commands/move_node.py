"""POST /nodes/{id}/move: ProjectTree.move."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import CanMoveNode, Permission


@dataclass(frozen=True)
class MoveNode(WriteCommand):
    node_id: int
    new_parent_id: Optional[int]
    position: int

    def required_permission(self) -> Permission:
        return CanMoveNode(self.node_id, self.new_parent_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
