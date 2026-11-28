"""ConversationalReviewerBackend: template method shared by every model backend.
review = open a fresh conversation (the one step a backend supplies) -> the configured ReviewMethod over it
(per-sentence by default; bulk when the factory passes BulkReview)."""
from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from ..kind_dispatch import ReviewByKind
from ..node_guess_screen import NodeGuessScreen
from ..review_conversation import ReviewConversation
from ..review_method import ReviewMethod
from ..sentence_review import SentenceBySentenceReview
from ..types import ReviewPacket, Verdict
from .interface import ReviewerBackend


class ConversationalReviewerBackend(ReviewerBackend):

    _review_method: Optional[ReviewMethod] = None

    def use_review_method(self, review_method: ReviewMethod) -> "ConversationalReviewerBackend":
        self._review_method = review_method
        return self

    def review(self, packet: ReviewPacket) -> Verdict:
        if self._review_method is None:
            self._review_method = ReviewByKind(SentenceBySentenceReview(), NodeGuessScreen())
        return self._review_method.run(packet, self._open_conversation())

    @abstractmethod
    def _open_conversation(self) -> ReviewConversation:
        """A conversation for one review."""
