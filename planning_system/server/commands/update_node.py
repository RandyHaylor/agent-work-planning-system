"""PATCH /nodes/{id}: ProjectTree.update(**fields)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import CanEditNode, Permission


@dataclass(frozen=True)
class UpdateNode(WriteCommand):
    node_id: int
    fields: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return CanEditNode(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
