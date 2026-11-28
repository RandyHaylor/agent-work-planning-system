"""POST /admin/halt {project_id?, reason?}, POST /admin/unhalt {project_id?}, GET /admin/halt: the admin's stop switch
(build log #68). Admin only; halt and un-halt work while halted."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import ReadCommand, WriteCommand
from .permissions import Permission, RoleIs

ADMIN_ONLY = RoleIs(("admin",))


@dataclass(frozen=True)
class HaltSystem(WriteCommand):
    project_id: Optional[int] = None         # None = the whole system
    reason: str = ""
    allowed_while_halted = True

    def required_permission(self) -> Permission:
        return ADMIN_ONLY

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.halt.halt(self.project_id, principal.agent_id or principal.role, self.reason)


@dataclass(frozen=True)
class UnhaltSystem(WriteCommand):
    project_id: Optional[int] = None
    allowed_while_halted = True

    def required_permission(self) -> Permission:
        return ADMIN_ONLY

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.halt.unhalt(self.project_id)


@dataclass(frozen=True)
class GetHaltState(ReadCommand):

    def required_permission(self) -> Permission:
        return ADMIN_ONLY

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.halt.state()
