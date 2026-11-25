"""POST /credentials/{id}/rotate: CredentialIssuer.rotate (keeps the id; log #17)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import CanManageCredential, Permission


@dataclass(frozen=True)
class RotateCredential(WriteCommand):
    credential_id: str

    def required_permission(self) -> Permission:
        return CanManageCredential(self.credential_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
