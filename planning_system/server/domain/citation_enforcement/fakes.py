"""Test support: FakeCitationEnforcement, a compact one-function version of the same rules (contract
tests run against it and the real one); consumers use it to test the gate's wiring."""
from __future__ import annotations

import re

from planning_system.errors import Invalid, NotFound
from planning_system.server.domain.references.citation_syntax import citations_in

from .claim_policy import ClaimPolicy
from .interface import CitationEnforcement
from .types import MAX_TITLE_LENGTH, CheckedClaim

_LOOKS_LIKE = re.compile(r"\[(?:ref|tmp)-[^\]]*\]")


class FakeCitationEnforcement(CitationEnforcement):
    def __init__(self, references, policy: ClaimPolicy | None = None):
        self._references = references
        self._policy = policy or ClaimPolicy.default()

    def check_content(self, text, tags):
        claim = [t for t in tags if t in self._policy.tags]
        if len(claim) != 1:
            raise Invalid(f"content needs exactly one claim tag: {', '.join(self._policy.tags)} (got: {list(tags)})")
        rule = self._policy.rule(claim[0])
        if rule.line_prefixes:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            prefixes = ", ".join(rule.line_prefixes)
            if not lines:
                raise Invalid(f'a "{rule.tag}" item needs a line starting with one of {prefixes}')
            bad = [line for line in lines if not line.startswith(rule.line_prefixes)]
            if bad:
                raise Invalid(f'a "{rule.tag}" item: every non-empty line must start with one of {prefixes}; '
                              f"bad line: {bad[0]!r}")
        citations = citations_in(text)
        good = {f"[{c.reference_id}:{c.start_line}-{c.end_line}]" for c in citations}
        for found in _LOOKS_LIKE.findall(text):
            if found not in good:
                raise Invalid(f'malformed citation "{found}": expected [reference-id:start-end]')
        problems, origins = [], []
        for c in citations:
            try:
                ref = self._references.get(c.reference_id, follow_superseded=False)
            except NotFound:
                problems.append(f"{c.reference_id} is a temp cache item: planning cite it first"
                                if c.reference_id.startswith("tmp-") else f"reference {c.reference_id} does not exist")
                continue
            if ref.superseded_by:
                problems.append(f"{ref.id} is superseded by {ref.superseded_by}; cite {ref.superseded_by}")
                continue
            count = len(ref.text.splitlines())
            if not 1 <= c.start_line <= c.end_line <= count:
                problems.append(f"lines {c.start_line}-{c.end_line} of {ref.id} are out of range (1-{count})")
                continue
            origins.append(ref.origin)
        if problems:
            raise Invalid("; ".join(problems))
        missing = [hint for group, hint in zip(rule.needs, rule.hints) if not set(origins) & group]
        if missing:
            raise Invalid(f'a "{rule.tag}" claim {"; ".join(missing)}. '
                          f'Found only: {", ".join(origins) or "no citations"}')
        if any(o not in rule.allowed for o in origins):
            raise Invalid(f'a "{rule.tag}" claim may cite only {", ".join(sorted(rule.allowed))}')
        return CheckedClaim(claim[0], tuple(citations), rule.reviewed)

    def check_title(self, title):
        stripped = title.strip()
        if not stripped or len(stripped) > MAX_TITLE_LENGTH or citations_in(stripped) \
                or stripped[-1] in ".!?":
            raise Invalid(f"title {title!r} must be a short noun phrase (1-{MAX_TITLE_LENGTH} chars, no citation, "
                          "not a sentence)")
