"""Types for citation_enforcement (spec: planning/05-spec-citation-enforcement-and-review.md)."""
from dataclasses import dataclass

from planning_system.server.domain.references import Citation

CLAIM_TAGS = ("requirement", "decision", "technical", "documentation", "plan", "note", "open_items")
OPEN_ITEMS = "open_items"
MAX_TITLE_LENGTH = 50


@dataclass(frozen=True)
class CheckedClaim:
    """What a content write passed the gate with: its one claim tag, the citations in its text, and whether
    a content review is opened for it (open_items: no, build log #61)."""
    claim_tag: str
    citations: tuple[Citation, ...]
    reviewed: bool = True
