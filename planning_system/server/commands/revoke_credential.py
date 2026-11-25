"""POST /credentials/{id}/revoke: CredentialIssuer.revoke (cascades)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanManageCredential, Permission


@dataclass(frozen=True)
class RevokeCredential(WriteCommand):
    credential_id: str

    def required_permission(self) -> Permission:
        return CanManageCredential(self.credential_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        services.issuer.revoke(principal, self.credential_id)
