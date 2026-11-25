"""POST /reviews/{id}/verdict {passed, reason, suggested_title?}: ReviewLedger.submit (holder only, 409
otherwise). The suggested title is recorded, never applied (only the planner edits nodes)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.domain.content_review.types import Verdict

from .command import WriteCommand
from .permissions import CanReviewRecord, Permission
from .take_review import reviewer_id


@dataclass(frozen=True)
class SubmitReviewVerdict(WriteCommand):
    review_id: str
    passed: bool
    reason: str
    suggested_title: Optional[str] = None

    def required_permission(self) -> Permission:
        return CanReviewRecord(self.review_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reviews.submit(self.review_id, reviewer_id(principal),
                                       Verdict(self.passed, self.reason, self.suggested_title))
