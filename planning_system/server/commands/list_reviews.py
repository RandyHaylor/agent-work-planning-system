"""GET /reviews?project_id=&status=&node_id=: ReviewLedger.list (the planner's view of failed reviews)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal
from planning_system.server.domain.content_review import STATUSES

from .command import ReadCommand
from .permissions import CanReviewProject, Permission


@dataclass(frozen=True)
class ListReviews(ReadCommand):
    project_id: int
    status: Optional[str] = None
    node_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.status is not None and self.status not in STATUSES:
            raise Invalid(f"status must be one of {', '.join(STATUSES)}")

    def required_permission(self) -> Permission:
        return CanReviewProject(self.project_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reviews.list(self.project_id, self.status, self.node_id)
