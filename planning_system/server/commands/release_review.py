"""POST /reviews/{id}/release: ReviewLedger.release (holder only); the record goes back to pending."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanReviewRecord, Permission
from .take_review import reviewer_id


@dataclass(frozen=True)
class ReleaseReview(WriteCommand):
    review_id: str

    def required_permission(self) -> Permission:
        return CanReviewRecord(self.review_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        services.reviews.release(self.review_id, reviewer_id(principal))
        return services.reviews.get(self.review_id)
