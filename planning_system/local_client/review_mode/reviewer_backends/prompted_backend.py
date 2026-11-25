"""PromptedReviewerBackend: template method shared by every backend that talks to a model in text.
review = build the prompt -> ask the model (the one step a backend supplies) -> parse the strict JSON verdict."""
from __future__ import annotations

from abc import abstractmethod

from ..review_prompt import build_review_prompt
from ..types import ReviewPacket, Verdict
from ..verdict_parser import parse_verdict
from .interface import ReviewerBackend


class PromptedReviewerBackend(ReviewerBackend):

    def review(self, packet: ReviewPacket) -> Verdict:
        return parse_verdict(self._ask(build_review_prompt(packet)))

    @abstractmethod
    def _ask(self, prompt: str) -> str:
        """The model's raw answer to the prompt. Raises ReviewerUnavailable on any backend failure."""
