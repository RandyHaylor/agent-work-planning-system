"""title_rules (private): SoT's deterministic title checks plus no citation and not a sentence. The
semantic ones (1-5 word noun phrase, no detail beyond the slice) are the reviewer's."""
from planning_system.contract import Invalid
from planning_system.server.domain.references.citation_format import citations_in

from .types import MAX_TITLE_LENGTH

SENTENCE_ENDINGS = (".", "!", "?")


def check_title(title: str) -> None:
    stripped = (title or "").strip()
    if not stripped:
        raise Invalid("title is empty: use a short generic noun phrase such as \"vendor placement\"")
    if len(stripped) > MAX_TITLE_LENGTH:
        raise Invalid(f"title is {len(stripped)} characters; at most {MAX_TITLE_LENGTH}: use a short generic "
                      "noun phrase and put the details in content")
    if citations_in(stripped):
        raise Invalid("title contains a citation: titles make no claims; put cited text in content")
    if stripped.endswith(SENTENCE_ENDINGS):
        raise Invalid(f"title {stripped!r} reads as a sentence: use a noun phrase without a trailing "
                      f"{' / '.join(SENTENCE_ENDINGS)}")
