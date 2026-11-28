"""claim_policy (private): claim tag -> the origins it needs and the origins it may cite. One table,
loadable from configuration so the tag set can grow without code changes elsewhere.

Row shape: {"needs": [...], "allowed": [...], "hint": "...", "line_prefixes": [...], "reviewed": bool}
- needs: a flat list of origins (at least one citation of any of them), or a list of groups (each group
  needs at least one citation of one of its origins; the "why" rule, build log #61). Empty = no citation.
- hint: one string, or one per group (the 422 names only the groups that are missing).
- line_prefixes: when set, every non-empty line must start with one of them (open_items, build log #61).
- reviewed: False = no content review is opened for it (default True)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from planning_system.server.domain.references import (ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE, ORIGIN_NODE,
                                                      ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE)

EVIDENCE_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE, ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE)
USER_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)
REFERENCE_ORIGINS = (ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE)

USER_HINT = "needs a user quote: cite a user_exchange or proposal_response reference (find the user's reply with `planning client exchanges`, sync it with `planning cite-exchange LOCAL_ID`, then read its lines with `planning references lines REF`)"
REFERENCE_HINT = ("needs a reference quote: cite a document or knowledge_base reference "
                  "(load the page, file or code through the reader and cite it)")
WHY_HINT = ("is missing a user quote (the why): cite a user_exchange or proposal_response reference where the "
            "user asked for or approved it (`planning client exchanges`, `planning cite-exchange LOCAL_ID`)")
PROOF_HINT = ("is missing a reference quote (the proof): cite a document or knowledge_base reference "
              "(load the page, file or code through the reader and cite it)")
OPEN_ITEM_PREFIXES = ("RESEARCH:", "ASK USER:", "VERIFY WITH USER:")

# allowed: every citation must be of one of these (origin "node" is never evidence; it may only sit
# alongside qualifying evidence, so it is allowed but never satisfies `needs`)
ANY_EVIDENCE = (*EVIDENCE_ORIGINS, ORIGIN_NODE)
DEFAULT_TABLE: Mapping[str, Mapping[str, Any]] = {
    "requirement": {"needs": USER_ORIGINS, "allowed": ANY_EVIDENCE, "hint": USER_HINT},
    "decision": {"needs": USER_ORIGINS, "allowed": ANY_EVIDENCE, "hint": USER_HINT},
    "technical": {"needs": (USER_ORIGINS, REFERENCE_ORIGINS), "allowed": ANY_EVIDENCE,
                  "hint": (WHY_HINT, PROOF_HINT)},
    "documentation": {"needs": REFERENCE_ORIGINS, "allowed": REFERENCE_ORIGINS, "hint": REFERENCE_HINT},
    "plan": {"needs": (USER_ORIGINS, REFERENCE_ORIGINS), "allowed": ANY_EVIDENCE,
             "hint": (WHY_HINT, PROOF_HINT)},
    "note": {"needs": (), "allowed": ANY_EVIDENCE, "hint": ""},
    "open_items": {"needs": (), "allowed": ANY_EVIDENCE, "hint": "", "line_prefixes": OPEN_ITEM_PREFIXES,
                   "reviewed": False},
}


@dataclass(frozen=True)
class ClaimRule:
    tag: str
    needs: tuple[frozenset, ...]        # every group needs at least one citation of one of its origins
    allowed: frozenset
    hints: tuple[str, ...]              # one per group
    line_prefixes: tuple[str, ...] = ()
    reviewed: bool = True


def _groups(needs: Sequence) -> tuple[frozenset, ...]:
    if not needs:
        return ()
    if all(isinstance(item, str) for item in needs):
        return (frozenset(needs),)
    return tuple(frozenset(group) for group in needs)


def _hints(hint: Any, count: int) -> tuple[str, ...]:
    if isinstance(hint, str):
        return (hint,) * count
    hints = tuple(str(h) for h in hint or ())
    return hints + ("",) * (count - len(hints))


def _rule(tag: str, row: Mapping[str, Any]) -> ClaimRule:
    needs = _groups(row.get("needs", ()))
    return ClaimRule(tag, needs, frozenset(row.get("allowed", ())), _hints(row.get("hint", ""), len(needs)),
                     tuple(row.get("line_prefixes", ())), bool(row.get("reviewed", True)))


class ClaimPolicy:
    """The tag table. ClaimPolicy.default() is the spec's table; from_mapping() reads the same shape
    from config ({tag: {"needs": [...], "allowed": [...], "hint": "...", ...}})."""

    def __init__(self, table: Mapping[str, Mapping[str, Any]]):
        self._rules = {tag: _rule(tag, row) for tag, row in table.items()}

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
