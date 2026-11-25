"""POST /nodes/{id}/content: CitationEnforcement.check_content (422 telling the agent what to fix) ->
ProjectTree.add_content -> ReviewLedger.open, in one transaction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .content_submission import open_review
from .permissions import CanAddContent, Permission


@dataclass(frozen=True)
class AddNodeContent(WriteCommand):
    node_id: int
    text: str
    tags: tuple[str, ...] = ()

    def required_permission(self) -> Permission:
        return CanAddContent(self.node_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        claim = services.enforcement.check_content(self.text, self.tags)
        content = services.tree.add_content(self.node_id, self.text, self.tags)
        return open_review(services, self.node_id, content, claim.claim_tag)
