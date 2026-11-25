"""POST /nodes/{id}/state: ProjectTree.set_state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanSetState, Permission


@dataclass(frozen=True)
class SetNodeState(WriteCommand):
    node_id: int
    state: str

    def required_permission(self) -> Permission:
        return CanSetState(self.node_id, self.state)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.tree.set_state(self.node_id, self.state)
