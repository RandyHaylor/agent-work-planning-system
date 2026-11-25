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


@dataclass(frozen=True)
class ReviewPacket:
    review_id: str
    node_title: str
    node_context_summary: str
    claim_tag: str
    claim_text: str
    citations: tuple[ResolvedCitation, ...]

    @classmethod
    def from_json(cls, data: dict) -> "ReviewPacket":
        return cls(str(data["review_id"]), str(data.get("node_title") or ""),
                   str(data.get("node_context_summary") or ""), str(data.get("claim_tag") or ""),
                   str(data.get("claim_text") or ""),
                   tuple(ResolvedCitation.from_json(c) for c in data.get("citations") or ()))


@dataclass(frozen=True)
class Verdict:                 # SoT PerOperationVerdict, one content item per review
    passed: bool
    reason: str
    suggested_title: Optional[str] = None


def _citation_text(value: Any) -> str:
    """The server sends the citation string; a structured citation is rendered in the same format."""
    if isinstance(value, dict) and {"reference_id", "start", "end"} <= value.keys():
        return f"[{value['reference_id']}:{value['start']}-{value['end']}]"
    return value if isinstance(value, str) else json.dumps(value)
