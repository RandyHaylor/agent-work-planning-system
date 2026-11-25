"""CitationEnforcementService: the real gate; composes claim_policy, citation_checker and title_rules."""
from __future__ import annotations

from typing import Optional

from planning_system.server.domain.references.interface import ReferenceLibrary

from .claim_policy import ClaimPolicy
from .interface import CitationEnforcement


class CitationEnforcementService(CitationEnforcement):
    def __init__(self, references: ReferenceLibrary, policy: Optional[ClaimPolicy] = None):
        self._references = references
        self._policy = policy or ClaimPolicy.default()

    def check_content(self, text, tags):
        raise NotImplementedError("level 7")

    def check_title(self, title):
        raise NotImplementedError("level 7")
