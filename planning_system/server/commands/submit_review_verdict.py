"""POST /reviews/{id}/verdict {passed, reason, suggested_title?, findings?}: ReviewLedger.submit (holder only, 409
otherwise). The suggested title is recorded, never applied (only the planner edits nodes). Supersede steps follow
a verdict: a quote check's findings become candidates; the last trial of a candidate opens its requirement
request (supersede_flow)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.domain.content_review import ReviewedWith, Verdict

from .command import WriteCommand
from .permissions import CanReviewRecord, Permission
from .supersede_flow import after_verdict
from .take_review import reviewer_id


@dataclass(frozen=True)
class SubmitReviewVerdict(WriteCommand):
    review_id: str
    passed: bool
    reason: str
    suggested_title: Optional[str] = None
    findings: tuple[str, ...] = ()
    reviewed_with: Optional[ReviewedWith] = None     # backend/model/profile/granularity/prompt version (log #70)

    def required_permission(self) -> Permission:
        return CanReviewRecord(self.review_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        record = services.reviews.submit(self.review_id, reviewer_id(principal),
                                         Verdict(self.passed, self.reason, self.suggested_title, self.findings,
                                                 self.reviewed_with))
        after_verdict(services, record)
        return record
