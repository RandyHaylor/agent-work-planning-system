"""GET /projects/{project_id}/open-items: the project's open items, a view by claim tag over existing content
(build log #61: "an explicit to-do list of items to research or to ask/verify with the user"). Not a new type:
content items tagged open_items, per node, with their non-empty lines."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.domain.citation_enforcement import OPEN_ITEMS

from .command import ReadCommand
from .permissions import CanReadNode, Permission


@dataclass(frozen=True)
class OpenItems:
    node_id: int
    node_title: str
    reference_id: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class ListOpenItems(ReadCommand):
    project_id: int

    def required_permission(self) -> Permission:
        return CanReadNode(self.project_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        found = []
        for node in services.tree.list_nodes(self.project_id):
            for item in services.tree.content(node.id):
                if OPEN_ITEMS in item.tags:
                    text = services.references.get(item.reference_id, follow_superseded=False).text
                    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
                    found.append(OpenItems(node.id, node.title, item.reference_id, lines))
        return found
