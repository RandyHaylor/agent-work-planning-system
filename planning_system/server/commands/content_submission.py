"""content_submission: the steps the two content commands share after the gate passes: open the review
record for the stored item and say "submitted for review", never "approved" (spec "Flow" 2-3)."""
from __future__ import annotations

from dataclasses import dataclass

SUBMITTED_MESSAGE = "submitted for review (not approved)"


@dataclass(frozen=True)
class SubmittedReview:
    id: str
    status: str


@dataclass(frozen=True)
class SubmittedContent:
    reference_id: str
    tags: frozenset
    review: SubmittedReview
    message: str = SUBMITTED_MESSAGE


def project_of(services, node_id: int) -> int:
    ancestors = services.tree.ancestors(node_id)
    return ancestors[0].id if ancestors else node_id


def open_review(services, node_id: int, content, claim_tag: str) -> SubmittedContent:
    record = services.reviews.open(project_of(services, node_id), node_id, content.reference_id, claim_tag)
    return SubmittedContent(content.reference_id, content.tags, SubmittedReview(record.id, record.status))
