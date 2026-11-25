"""GET /me: the authenticated Principal."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import ReadCommand
from .permissions import Authenticated, Permission


@dataclass(frozen=True)
class GetCurrentPrincipal(ReadCommand):
    pass

    def required_permission(self) -> Permission:
        return Authenticated()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return principal
