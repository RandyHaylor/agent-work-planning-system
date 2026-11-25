"""POST /nodes/{id}/assign: TaskAssigner.assign (ProjectTree.assign + CredentialIssuer.mint of a
worker token scoped to the node, in this one transaction). Returns an Assignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanAssign, Permission


@dataclass(frozen=True)
class AssignTask(WriteCommand):
    node_id: int
    agent_id: str
    branch: str

    def required_permission(self) -> Permission:
        return CanAssign(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.task_assigner.assign(principal, self.node_id, self.agent_id, self.branch)
