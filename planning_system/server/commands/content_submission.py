"""content_submission: the steps the two content commands share after the gate passes: open the review
record for the stored item and say "submitted for review", never "approved" (spec "Flow" 2-3). A claim the
gate marks as not reviewed (open_items, build log #61) is stored with no review record."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SUBMITTED_MESSAGE = "submitted for review (not approved)"
NOT_REVIEWED_MESSAGE = "stored; open items are not reviewed (list them with `planning open-items`)"


@dataclass(frozen=True)
class SubmittedReview:
    id: str
    status: str


@dataclass(frozen=True)
class SubmittedContent:
    reference_id: str
    tags: frozenset
    review: Optional[SubmittedReview]
    message: str = SUBMITTED_MESSAGE


def project_of(services, node_id: int) -> int:
    ancestors = services.tree.ancestors(node_id)
    return ancestors[0].id if ancestors else node_id


def submit(services, node_id: int, content, claim) -> SubmittedContent:
    """claim: the gate's CheckedClaim."""
    if not claim.reviewed:
        return SubmittedContent(content.reference_id, content.tags, None, NOT_REVIEWED_MESSAGE)
    record = services.reviews.open(project_of(services, node_id), node_id, content.reference_id, claim.claim_tag)
    return SubmittedContent(content.reference_id, content.tags, SubmittedReview(record.id, record.status))
