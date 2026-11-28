"""Types for content_review: a review record about one target (a content item, or a whole node for the guess
screen, build log #60 (5)); never a node state or node type. The packet a reviewer gets (quotes already resolved
and inlined, SoT's "no Read needed"), and the verdict."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from planning_system.server.domain.references import Citation

PENDING, TAKEN, PASSED, FAILED, SUPERSEDED = "pending", "taken", "passed", "failed", "superseded"
STATUSES = (PENDING, TAKEN, PASSED, FAILED, SUPERSEDED)
BLOCKING_STATUSES = frozenset({PENDING, TAKEN, FAILED})   # a node can't be "done" with these (log #50)
DEFAULT_LEASE = timedelta(minutes=10)

# what a record is about
TARGET_CONTENT = "content"           # one content item: its claim against its citations
TARGET_NODE = "node"                 # the whole node: title + summary + every item (guess screen)
TARGET_KINDS = (TARGET_CONTENT, TARGET_NODE)


@dataclass(frozen=True)
class ReviewRecord:
    id: str                          # "rev-<uuid4>"
    project_id: int
    node_id: int
    content_reference_id: Optional[str]   # the content item under review; None for a node review
    claim_tag: str                   # "" for a node review
    status: str
    reviewer: Optional[str]          # agent id holding / having held it
    taken_at: Optional[datetime]
    reason: str                      # reviewer's reason (SoT: <= 15 words)
    suggested_title: Optional[str]   # SoT's amended_short_title; NOT auto-applied
    created_at: datetime
    decided_at: Optional[datetime]
    target_kind: str = TARGET_CONTENT


@dataclass(frozen=True)
class ResolvedCitation:
    citation: Citation
    origin: str
    quoted_text: str                 # exact lines
    pre_text: str                    # user_exchange only: what came before the quoted lines
    full_text: str                   # user_exchange/proposal_response: whole entry; documents: ""


@dataclass(frozen=True)
class PacketContentItem:
    """One of a node's content items, in a node packet."""
    reference_id: str
    tags: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class ReviewPacket:
    review_id: str
    node_title: str
    node_context_summary: str
    claim_tag: str                   # content packets; "" for node packets
    claim_text: str                  # content packets; "" for node packets
    citations: tuple[ResolvedCitation, ...]
    kind: str = TARGET_CONTENT
    content_items: tuple[PacketContentItem, ...] = ()   # node packets: every current item, in order


@dataclass(frozen=True)
class Verdict:                       # SoT PerOperationVerdict, one op per review
    passed: bool
    reason: str
    suggested_title: Optional[str] = None
