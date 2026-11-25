"""POST /references/user-exchange: ReferenceLibrary.store_user_exchange (quote key only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanSubmitUserQuote, Permission


@dataclass(frozen=True)
class StoreUserExchange(WriteCommand):
    session_id: str
    user_message: str
    pre_text: str

    def required_permission(self) -> Permission:
        return CanSubmitUserQuote()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.references.store_user_exchange(self.session_id, self.user_message, self.pre_text)
