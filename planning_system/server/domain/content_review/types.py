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
TARGET_TRIAL = "trial"               # a content item against a NEWER copy of a reference it cites (supersede)
TARGET_QUOTE_CHECK = "quote_check"   # a new user quote against every user quote cited in the project
TARGET_KINDS = (TARGET_CONTENT, TARGET_NODE, TARGET_TRIAL, TARGET_QUOTE_CHECK)
NODE_GATING_KINDS = frozenset({TARGET_CONTENT, TARGET_NODE})   # only these keep a node from "done"


@dataclass(frozen=True)
class ReviewedWith:
    """Which reviewer produced a verdict (build log #70); every field as the client reports it."""
    backend: Optional[str] = None            # local_llm | claude_code
    model: Optional[str] = None
    profile: Optional[str] = None            # reviewer profile name; None when set by flags only
    granularity: Optional[str] = None        # per_sentence | bulk | both
    prompt_version: Optional[str] = None     # hash of the client's review prompt texts

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["ReviewedWith"]:
        if not data:
            return None
        return cls(**{name: data.get(name) for name in cls.__dataclass_fields__})


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
    against_reference_id: Optional[str] = None   # trial: the newer copy; quote_check: the new user quote
    replaces_reference_id: Optional[str] = None  # trial: the older reference the item cites
    candidate_id: Optional[str] = None           # trial: the supersede candidate it tries out
    findings: tuple[str, ...] = ()               # quote_check: the earlier quotes (reference ids) it changes
    reviewed_with: Optional[ReviewedWith] = None  # the reviewer of the submitted verdict (migration 0006)


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
class Comparison:
    """trial packets: one citation of the old reference and where its lines sit in the newer copy."""
    citation: Citation
    old_text: str
    new_text: str                    # "" when every cited line was deleted
    new_start: Optional[int]
    new_end: Optional[int]


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
    against_reference_id: Optional[str] = None          # trial / quote_check
    against_text: str = ""                              # trial: the whole newer copy
    comparisons: tuple[Comparison, ...] = ()            # trial: old cited lines -> lines in the newer copy
    subject: Optional[ResolvedCitation] = None          # quote_check: the new user statement as cited


@dataclass(frozen=True)
class Verdict:                       # SoT PerOperationVerdict, one op per review
    passed: bool
    reason: str
    suggested_title: Optional[str] = None
    findings: tuple[str, ...] = ()   # quote_check: reference ids of the earlier quotes the new one changes
    reviewed_with: Optional[ReviewedWith] = None
