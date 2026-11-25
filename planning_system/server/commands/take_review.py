"""POST /reviews/take {project_id}: ReviewLedger.take_next -> the packet, or None (the route answers 204)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import CanReviewProject, Permission


def reviewer_id(principal: Principal) -> str:
    """The agent id; admin (no agent id) reviews as "admin"."""
    return principal.agent_id or principal.role


@dataclass(frozen=True)
class TakeReview(WriteCommand):
    project_id: int

    def required_permission(self) -> Permission:
        return CanReviewProject(self.project_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.reviews.take_next(self.project_id, reviewer_id(principal))
