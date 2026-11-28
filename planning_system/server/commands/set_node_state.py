"""POST /nodes/{id}/state: ProjectTree.set_state. "done" is rejected while any of the node's reviews (content
items, build log #50, or the whole-node guess screen, #60 (5)) are pending, taken or failed."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal
from planning_system.server.domain.project_tree import DONE

from .command import WriteCommand
from .permissions import CanSetState, Permission


@dataclass(frozen=True)
class SetNodeState(WriteCommand):
    node_id: int
    state: str

    def required_permission(self) -> Permission:
        return CanSetState(self.node_id, self.state)

    def run(self, services, principal: Optional[Principal]) -> Any:
        if self.state == DONE:
            blocking = services.reviews.blocking_for_node(self.node_id)
            if blocking:
                listed = ", ".join(f"{r.id} ({r.status}, " + (f"content {r.content_reference_id})"
                                                               if r.content_reference_id else "whole node)")
                                   for r in blocking)
                raise Invalid(f"node {self.node_id} can't be done while reviews are pending or failed: "
                              f"{listed}. Wait for pending reviews; fix failed content (replace it) or the node's "
                              "title/summary first")
        return services.tree.set_state(self.node_id, self.state)
