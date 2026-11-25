"""POST /admin/sessions: AdminSessions.start(password); runs with no principal."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import NoPrincipalNeeded, Permission


@dataclass(frozen=True)
class StartAdminSession(WriteCommand):
    password: str

    def required_permission(self) -> Permission:
        return NoPrincipalNeeded()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
