"""Types for citation_enforcement (spec: planning/05-spec-citation-enforcement-and-review.md)."""
from dataclasses import dataclass

from planning_system.server.domain.references.types import Citation

CLAIM_TAGS = ("requirement", "decision", "technical", "documentation", "plan", "note")
MAX_TITLE_LENGTH = 50


@dataclass(frozen=True)
class CheckedClaim:
    """What a content write passed the gate with: its one claim tag and the citations in its text."""
    claim_tag: str
    citations: tuple[Citation, ...]
