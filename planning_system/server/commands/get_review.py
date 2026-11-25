"""GET /reviews/{id}: ReviewLedger.get (one review record; used by `planning review show`)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import ReadCommand
from .permissions import CanReviewRecord, Permission


@dataclass(frozen=True)
class GetReview(ReadCommand):
    review_id: str

    def required_permission(self) -> Permission:
        return CanReviewRecord(self.review_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reviews.get(self.review_id)
