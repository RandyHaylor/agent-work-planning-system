"""PUT /nodes/{id}/content/{reference_id}: ProjectTree.replace_content."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanAddContent, Permission


@dataclass(frozen=True)
class ReplaceNodeContent(WriteCommand):
    node_id: int
    reference_id: str
    text: str

    def required_permission(self) -> Permission:
        return CanAddContent(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.tree.replace_content(self.node_id, self.reference_id, self.text)
