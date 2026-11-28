"""CitationEnforcementService: the real gate; composes claim_policy, citation_checker and title_rules.
Stages in order, first failing stage -> Invalid: claim tag, parse, resolve + range (all reported), origin."""
from __future__ import annotations

from typing import Optional

from planning_system.errors import Invalid
from planning_system.server.domain.references import ReferenceLibrary

from . import title_rules
from .citation_checker import CitationChecker
from .claim_policy import ClaimPolicy
from .interface import CitationEnforcement
from .types import CheckedClaim


class CitationEnforcementService(CitationEnforcement):
    def __init__(self, references: ReferenceLibrary, policy: Optional[ClaimPolicy] = None):
        self._checker = CitationChecker(references)
        self._policy = policy or ClaimPolicy.default()

    def check_content(self, text, tags):
        tags = list(tags)
        claim_tags = [t for t in tags if t in self._policy.tags]
        if len(claim_tags) != 1:
            raise Invalid(f"content needs exactly one claim tag: {', '.join(self._policy.tags)} (got: {tags})")
        rule = self._policy.rule(claim_tags[0])
        citations = self._checker.parse(text)
        origins = self._checker.origins(citations)
        self._checker.check_origins(rule, origins)
        return CheckedClaim(rule.tag, citations)

    def check_title(self, title):
        title_rules.check_title(title)
