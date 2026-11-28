"""ConversationalReviewerBackend: template method shared by every model backend.
review = open a fresh conversation (the one step a backend supplies) -> optional conversation decorator (the review
log's recorder, build log #70) -> the configured ReviewMethod over it (per-sentence by default; bulk when the factory
passes BulkReview)."""
from __future__ import annotations

from abc import abstractmethod
from typing import Callable, Optional

from ..kind_dispatch import ReviewByKind
from ..node_guess_screen import NodeGuessScreen
from ..review_conversation import ReviewConversation
from ..review_method import ReviewMethod
from ..sentence_review import SentenceBySentenceReview
from ..types import ReviewPacket, Verdict
from .interface import ReviewerBackend

ConversationDecorator = Callable[[ReviewConversation], ReviewConversation]


class ConversationalReviewerBackend(ReviewerBackend):

    _review_method: Optional[ReviewMethod] = None
    _conversation_decorator: Optional[ConversationDecorator] = None

    def use_review_method(self, review_method: ReviewMethod) -> "ConversationalReviewerBackend":
        self._review_method = review_method
        return self

    def use_conversation_decorator(self, decorate: ConversationDecorator) -> "ConversationalReviewerBackend":
        self._conversation_decorator = decorate
        return self

    def review(self, packet: ReviewPacket) -> Verdict:
        if self._review_method is None:
            self._review_method = ReviewByKind(SentenceBySentenceReview(), NodeGuessScreen())
        conversation = self._open_conversation()
        if self._conversation_decorator is not None:
            conversation = self._conversation_decorator(conversation)
        return self._review_method.run(packet, conversation)

    @abstractmethod
    def _open_conversation(self) -> ReviewConversation:
        """A conversation for one review."""
