"""claim_policy (private): claim tag -> the origins it needs and the origins it may cite. One table,
loadable from configuration so the tag set can grow without code changes elsewhere."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from planning_system.server.domain.references import (ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE, ORIGIN_NODE,
                                                      ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE)

EVIDENCE_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE, ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE)
USER_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)
REFERENCE_ORIGINS = (ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE)

USER_HINT = "needs a user quote: cite a user_exchange or proposal_response reference (find the user's reply with `planning client exchanges`, sync it with `planning cite-exchange LOCAL_ID`, then read its lines with `planning references lines REF`)"
REFERENCE_HINT = ("needs a reference quote: cite a document or knowledge_base reference "
                  "(load the page, file or code through the reader and cite it)")

# needs: at least one citation of one of these origins (empty = no citation needed)
# allowed: every citation must be of one of these (origin "node" is never evidence; it may only sit
# alongside qualifying evidence, so it is allowed but never satisfies `needs`)
DEFAULT_TABLE: Mapping[str, Mapping[str, Any]] = {
    "requirement": {"needs": USER_ORIGINS, "allowed": (*EVIDENCE_ORIGINS, ORIGIN_NODE), "hint": USER_HINT},
    "decision": {"needs": USER_ORIGINS, "allowed": (*EVIDENCE_ORIGINS, ORIGIN_NODE), "hint": USER_HINT},
    "technical": {"needs": REFERENCE_ORIGINS, "allowed": (*EVIDENCE_ORIGINS, ORIGIN_NODE),
                  "hint": REFERENCE_HINT},
    "documentation": {"needs": REFERENCE_ORIGINS, "allowed": REFERENCE_ORIGINS, "hint": REFERENCE_HINT},
    "plan": {"needs": EVIDENCE_ORIGINS, "allowed": (*EVIDENCE_ORIGINS, ORIGIN_NODE),
             "hint": "needs evidence: cite at least one user quote or document reference"},
    "note": {"needs": (), "allowed": (*EVIDENCE_ORIGINS, ORIGIN_NODE), "hint": ""},
}


@dataclass(frozen=True)
class ClaimRule:
    tag: str
    needs: frozenset
    allowed: frozenset
    hint: str


class ClaimPolicy:
    """The tag table. ClaimPolicy.default() is the spec's table; from_mapping() reads the same shape
    from config ({tag: {"needs": [...], "allowed": [...], "hint": "..."}})."""

    def __init__(self, table: Mapping[str, Mapping[str, Any]]):
        self._rules = {tag: ClaimRule(tag, frozenset(row.get("needs", ())), frozenset(row.get("allowed", ())),
                                      str(row.get("hint", ""))) for tag, row in table.items()}

    @classmethod
    def default(cls) -> "ClaimPolicy":
        return cls(DEFAULT_TABLE)

    @classmethod
    def from_mapping(cls, table: Optional[Mapping[str, Mapping[str, Any]]]) -> "ClaimPolicy":
        return cls(table) if table else cls.default()

    @property
    def tags(self) -> tuple[str, ...]:
        return tuple(self._rules)

    def rule(self, tag: str) -> ClaimRule:
        return self._rules[tag]
