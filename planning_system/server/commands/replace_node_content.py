"""PUT /nodes/{id}/content/{reference_id}: gate -> ProjectTree.replace_content -> the old item's reviews
superseded -> a new review opened. tags None keeps the old item's tags (they carry its claim tag)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import NotFound, Principal

from .command import WriteCommand
from .content_submission import open_review
from .permissions import CanAddContent, Permission


@dataclass(frozen=True)
class ReplaceNodeContent(WriteCommand):
    node_id: int
    reference_id: str
    text: str
    tags: Optional[tuple[str, ...]] = None

    def required_permission(self) -> Permission:
        return CanAddContent(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        tags = self.tags if self.tags is not None else self._old_tags(services)
        claim = services.enforcement.check_content(self.text, tags)
        content = services.tree.replace_content(self.node_id, self.reference_id, self.text, tags)
        services.reviews.supersede_for(self.reference_id)
        return open_review(services, self.node_id, content, claim.claim_tag)

    def _old_tags(self, services) -> tuple[str, ...]:
        old = next((c for c in services.tree.content(self.node_id) if c.reference_id == self.reference_id), None)
        if old is None:
            raise NotFound(f"content {self.reference_id} on node {self.node_id}")
        return tuple(sorted(old.tags))
