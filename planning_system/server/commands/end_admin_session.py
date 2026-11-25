"""DELETE /admin/sessions: ends the caller's own admin session (the route passes its Bearer token,
since Principal carries no credential id)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import RoleIs, Permission


@dataclass(frozen=True)
class EndAdminSession(WriteCommand):
    presented_token: str

    def required_permission(self) -> Permission:
        return RoleIs(("admin",))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
