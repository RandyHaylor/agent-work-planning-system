"""GET /nodes/{id}: ProjectTree.get."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import ReadCommand, hollow
from .permissions import CanReadNode, Permission


@dataclass(frozen=True)
class GetNode(ReadCommand):
    node_id: int

    def required_permission(self) -> Permission:
        return CanReadNode(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
