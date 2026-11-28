"""PATCH /nodes/{id}: ProjectTree.update(**fields); a changed title or context summary opens a whole-node review."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .content_submission import open_node_review
from .permissions import CanEditNode, Permission


@dataclass(frozen=True)
class UpdateNode(WriteCommand):
    node_id: int
    fields: Mapping[str, Any] = field(default_factory=dict)

    def required_permission(self) -> Permission:
        return CanEditNode(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        if "title" in self.fields:
            services.enforcement.check_title(self.fields["title"])
        before = services.tree.get(self.node_id)
        updated = services.tree.update(self.node_id, **self.fields)
        if (updated.title, updated.context_summary) != (before.title, before.context_summary):
            open_node_review(services, self.node_id)          # guess screen, build log #60 (5)
        return updated
