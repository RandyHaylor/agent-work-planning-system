"""DELETE /admin/sessions: ends the caller's own admin session, found through the credential id the
authenticator put on the Principal (build log #40)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal

from .command import WriteCommand
from .permissions import RoleIs, Permission


@dataclass(frozen=True)
class EndAdminSession(WriteCommand):
    allowed_while_halted = True

    def required_permission(self) -> Permission:
        return RoleIs(("admin",))

    def run(self, services, principal: Optional[Principal]) -> Any:
        if principal is None or principal.credential_id is None:
            raise Invalid("no session credential on this request")
        services.admin_sessions.end(principal.credential_id)
