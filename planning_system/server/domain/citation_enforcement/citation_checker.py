"""citation_checker (private): parse -> resolve -> range -> origin, over ReferenceLibrary. Stages 2-5 of
the spec; resolve and range problems are collected so every bad citation is reported in one message."""
from __future__ import annotations

import re

from planning_system.errors import Invalid, NotFound
from planning_system.server.domain.references.citation_syntax import citations_in, format_citation
from planning_system.server.domain.references import ReferenceLibrary
from planning_system.server.domain.references import Citation

from .claim_policy import ClaimRule

# bracketed text that looks like a citation (a reference or temp id, then ":"); ids are ref-/tmp- (log #39)
_CITATION_LIKE = re.compile(r"\[(?:ref|tmp)-[^\]\s]*\]")
TEMP_PREFIX = "tmp-"


class CitationChecker:
    def __init__(self, references: ReferenceLibrary):
        self._references = references

    def parse(self, text: str) -> tuple[Citation, ...]:
        citations = tuple(citations_in(text))
        well_formed = {format_citation(c) for c in citations}
        for found in _CITATION_LIKE.findall(text):
            if found not in well_formed:
                raise Invalid(f'malformed citation "{found}": expected [reference-id:start-end]')
        return citations

    def origins(self, citations: tuple[Citation, ...]) -> list[str]:
        """The origin of each citation; Invalid naming every unresolvable or out-of-range one."""
        problems, origins = [], []
        for citation in citations:
            problem, origin = self._check_one(citation)
            if problem:
                problems.append(problem)
            else:
                origins.append(origin)
        if problems:
            raise Invalid("; ".join(problems))
        return origins

    def _check_one(self, citation: Citation) -> tuple[str, str]:
        ref_id, shown = citation.reference_id, format_citation(citation)
        try:
            ref = self._references.get(ref_id, follow_superseded=False)
        except NotFound:
            if ref_id.startswith(TEMP_PREFIX):
                return (f"{ref_id} is a temp cache item: cite it first (planning cite {ref_id} START END) "
                        "and use the returned reference id"), ""
            return f"reference {ref_id} does not exist", ""
        if ref.superseded_by:
            return f"{ref_id} is superseded by {ref.superseded_by}; cite {ref.superseded_by}", ""
        line_count = len(ref.text.splitlines())
        if not 1 <= citation.start_line <= citation.end_line <= line_count:
            return (f"{shown}: lines {citation.start_line}-{citation.end_line} are out of range; "
                    f"{ref_id} has {line_count} lines (1-{line_count})"), ""
        return "", ref.origin

    @staticmethod
    def check_origins(rule: ClaimRule, origins: list[str]) -> None:
        if rule.needs and not set(origins) & rule.needs:
            found = ", ".join(sorted(set(origins))) if origins else "no citations"
            raise Invalid(f'a "{rule.tag}" claim {rule.hint}. Found only: {found}')
        not_allowed = sorted({o for o in origins if o not in rule.allowed})
        if not_allowed:
            raise Invalid(f'a "{rule.tag}" claim may cite only {" or ".join(sorted(rule.allowed))} references; '
                          f"remove or replace the {', '.join(not_allowed)} citation(s)")
