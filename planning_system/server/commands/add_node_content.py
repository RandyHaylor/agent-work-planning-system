"""POST /nodes/{id}/content: ProjectTree.add_content."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanAddContent, Permission


@dataclass(frozen=True)
class AddNodeContent(WriteCommand):
    node_id: int
    text: str
    tags: tuple[str, ...] = ()

    def required_permission(self) -> Permission:
        return CanAddContent(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.tree.add_content(self.node_id, self.text, self.tags)
