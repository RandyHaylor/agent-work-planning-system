"""citation_format: the citation string agents write into node text: `[<reference id>:<start>-<end>]`
(1-based, inclusive lines; build log #40). Parse, format, and find the citations inside a text."""
import re

from planning_system.errors import Invalid

from .types import Citation

_CITATION = re.compile(r"\[(?P<ref>[A-Za-z0-9_.-]+):(?P<start>\d+)-(?P<end>\d+)\]")


def format_citation(citation: Citation) -> str:
    return f"[{citation.reference_id}:{citation.start_line}-{citation.end_line}]"


def parse_citation(text: str) -> Citation:
    """Exactly one citation (surrounding whitespace allowed); Invalid otherwise."""
    match = _CITATION.fullmatch(text.strip())
    if match is None:
        raise Invalid(f"not a citation (expected [reference-id:start-end]): {text!r}")
    return Citation(match["ref"], int(match["start"]), int(match["end"]))


def citations_in(text: str) -> list[Citation]:
    return [Citation(m["ref"], int(m["start"]), int(m["end"])) for m in _CITATION.finditer(text)]


def cites(text: str, reference_id: str) -> bool:
    return any(c.reference_id == reference_id for c in citations_in(text))
