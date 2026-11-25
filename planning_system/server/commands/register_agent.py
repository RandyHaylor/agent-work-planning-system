"""POST /agents: AgentRegistry.register(agent_id, **metadata)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import Authenticated, Permission


@dataclass(frozen=True)
class RegisterAgent(WriteCommand):
    agent_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return Authenticated()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
