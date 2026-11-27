"""ConversationalReviewerBackend: template method shared by every model backend.
review = open a fresh conversation (the one step a backend supplies) -> SentenceBySentenceReview over it."""
from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from ..review_conversation import ReviewConversation
from ..sentence_review import SentenceBySentenceReview
from ..types import ReviewPacket, Verdict
from .interface import ReviewerBackend


class ConversationalReviewerBackend(ReviewerBackend):

    _review: Optional[SentenceBySentenceReview] = None

    def review(self, packet: ReviewPacket) -> Verdict:
        if self._review is None:
            self._review = SentenceBySentenceReview()
        return self._review.run(packet, self._open_conversation())

    @abstractmethod
    def _open_conversation(self) -> ReviewConversation:
        """A conversation for one review."""
