"""review_mode types: the client's view of a review packet and a verdict
(05-spec-citation-enforcement-and-review.md "Types / public interfaces"), plus the backend errors."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


class ReviewerUnavailable(Exception):
    """The reviewer backend could not be reached or failed to answer."""


class UnparseableVerdict(Exception):
    """The reviewer answered, but not with the strict JSON verdict."""


@dataclass(frozen=True)
class ResolvedCitation:
    citation: str              # "[<reference id>:<start>-<end>]"
    origin: str
    quoted_text: str           # the exact cited lines
    pre_text: str = ""         # user_exchange only: what the agent said before (SoT PRE-INPUT CONTEXT)
    full_text: str = ""        # user_exchange/proposal_response: whole entry; documents: ""

    @classmethod
    def from_json(cls, data: dict) -> "ResolvedCitation":
        return cls(_citation_text(data.get("citation")), str(data.get("origin") or ""),
                   str(data.get("quoted_text") or ""), str(data.get("pre_text") or ""),
                   str(data.get("full_text") or ""))

    @property
    def reference_id(self) -> str:
        return self.citation.strip("[]").rsplit(":", 1)[0]


KIND_CONTENT = "content"      # one content item's claim against its citations
KIND_NODE = "node"            # the whole node, guess screen (build log #60 (5))
KIND_TRIAL = "trial"          # an item's claim against a newer copy of a reference (supersede trial review)
KIND_QUOTE_CHECK = "quote_check"   # a new user quote against every user quote cited in the project


@dataclass(frozen=True)
class Comparison:
    """trial packets: one citation of the older reference and its diff-matched lines in the newer copy."""
    citation: str
    old_text: str
    new_text: str             # "" when every cited line was deleted

    @classmethod
    def from_json(cls, data: dict) -> "Comparison":
        return cls(_citation_text(data.get("citation")), str(data.get("old_text") or ""),
                   str(data.get("new_text") or ""))


@dataclass(frozen=True)
class PacketContentItem:
    reference_id: str
    tags: tuple[str, ...]
    text: str

    @classmethod
    def from_json(cls, data: dict) -> "PacketContentItem":
        return cls(str(data.get("reference_id") or ""), tuple(str(t) for t in data.get("tags") or ()),
                   str(data.get("text") or ""))


@dataclass(frozen=True)
class ReviewPacket:
    review_id: str
    node_title: str
    node_context_summary: str
    claim_tag: str
    claim_text: str
    citations: tuple[ResolvedCitation, ...]
    kind: str = KIND_CONTENT
    content_items: tuple[PacketContentItem, ...] = ()     # node packets: every current content item
    against_reference_id: str = ""                        # trial: the newer copy; quote_check: the new quote
    against_text: str = ""                                # trial: the whole newer copy
    comparisons: tuple[Comparison, ...] = ()              # trial: old cited lines -> lines in the newer copy
    subject: Optional[ResolvedCitation] = None            # quote_check: the new user statement as cited

    @classmethod
    def from_json(cls, data: dict) -> "ReviewPacket":
        return cls(str(data["review_id"]), str(data.get("node_title") or ""),
                   str(data.get("node_context_summary") or ""), str(data.get("claim_tag") or ""),
                   str(data.get("claim_text") or ""),
                   tuple(ResolvedCitation.from_json(c) for c in data.get("citations") or ()),
                   str(data.get("kind") or KIND_CONTENT),
                   tuple(PacketContentItem.from_json(i) for i in data.get("content_items") or ()),
                   str(data.get("against_reference_id") or ""), str(data.get("against_text") or ""),
                   tuple(Comparison.from_json(c) for c in data.get("comparisons") or ()),
                   ResolvedCitation.from_json(data["subject"]) if data.get("subject") else None)


@dataclass(frozen=True)
class ReviewerIdentity:
    """Which reviewer answered (build log #70): sent with every verdict and written to every review log record."""
    backend: str
    model: Optional[str]
    profile: Optional[str]          # None when chosen by flags only
    granularity: str                # per_sentence | bulk | both
    prompt_version: str

    def as_dict(self) -> dict:
        return {"backend": self.backend, "model": self.model, "profile": self.profile,
                "granularity": self.granularity, "prompt_version": self.prompt_version}


@dataclass(frozen=True)
class Verdict:                 # SoT PerOperationVerdict, one content item per review
    passed: bool
    reason: str
    suggested_title: Optional[str] = None
    findings: tuple[str, ...] = ()     # quote_check: reference ids of the earlier quotes the new one changes


def _citation_text(value: Any) -> str:
    """The server sends the citation string; a structured citation is rendered in the same format."""
    if isinstance(value, dict) and {"reference_id", "start", "end"} <= value.keys():
        return f"[{value['reference_id']}:{value['start']}-{value['end']}]"
    if isinstance(value, dict) and {"reference_id", "start_line", "end_line"} <= value.keys():   # server's Citation
        return f"[{value['reference_id']}:{value['start_line']}-{value['end_line']}]"
    return value if isinstance(value, str) else json.dumps(value)
