"""Types for content_review: a review record about one content item (not a node state), the packet a
reviewer gets (quotes already resolved and inlined, SoT's "no Read needed"), and the verdict."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from planning_system.server.domain.references.types import Citation

PENDING, TAKEN, PASSED, FAILED, SUPERSEDED = "pending", "taken", "passed", "failed", "superseded"
STATUSES = (PENDING, TAKEN, PASSED, FAILED, SUPERSEDED)
BLOCKING_STATUSES = frozenset({PENDING, TAKEN, FAILED})   # a node can't be "done" with these (log #50)
REVIEW_TASK_LABEL = "review"
DEFAULT_LEASE = timedelta(minutes=10)


@dataclass(frozen=True)
class ReviewRecord:
    id: str                          # "rev-<uuid4>"
    project_id: int
    node_id: int
    content_reference_id: str        # the node content item under review
    claim_tag: str
    status: str
    reviewer: Optional[str]          # agent id holding / having held it
    taken_at: Optional[datetime]
    reason: str                      # reviewer's reason (SoT: <= 15 words)
    suggested_title: Optional[str]   # SoT's amended_short_title; NOT auto-applied
    created_at: datetime
    decided_at: Optional[datetime]


@dataclass(frozen=True)
class ResolvedCitation:
    citation: Citation
    origin: str
    quoted_text: str                 # exact lines
    pre_text: str                    # user_exchange only: what came before the quoted lines
    full_text: str                   # user_exchange/proposal_response: whole entry; documents: ""


@dataclass(frozen=True)
class ReviewPacket:
    review_id: str
    node_title: str
    node_context_summary: str
    claim_tag: str
    claim_text: str
    citations: tuple[ResolvedCitation, ...]


@dataclass(frozen=True)
class Verdict:                       # SoT PerOperationVerdict, one op per review
    passed: bool
    reason: str
    suggested_title: Optional[str] = None
