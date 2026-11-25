"""POST /credentials/quote-key: CredentialIssuer.mint_quote_key (admin only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from.command import WriteCommand, hollow
from .permissions import RoleIs, Permission


@dataclass(frozen=True)
class MintQuoteKey(WriteCommand):
    install_label: str

    def required_permission(self) -> Permission:
        return RoleIs(("admin",))

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
