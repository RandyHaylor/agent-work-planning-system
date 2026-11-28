"""POST /admin/sessions: AdminSessions.start(password); runs with no principal."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import NoPrincipalNeeded, Permission


@dataclass(frozen=True)
class StartAdminSession(WriteCommand):
    password: str
    allowed_while_halted = True      # the admin must be able to log in to un-halt

    def required_permission(self) -> Permission:
        return NoPrincipalNeeded()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.admin_sessions.start(self.password)
