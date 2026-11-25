"""POST /credentials: CredentialIssuer.mint (planner|worker)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanMint, Permission


@dataclass(frozen=True)
class MintCredential(WriteCommand):
    role: str
    project_id: Optional[int]
    scope_node_id: Optional[int]
    agent_id: Optional[str]

    def required_permission(self) -> Permission:
        return CanMint(self.role, self.project_id, self.scope_node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.issuer.mint(principal, self.role, self.project_id, self.scope_node_id,
                                    self.agent_id)
