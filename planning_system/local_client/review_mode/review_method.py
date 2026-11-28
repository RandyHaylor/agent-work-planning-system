"""ReviewMethod: how one review is asked over a conversation (strategy). Granularity names:
per_sentence -> SentenceBySentenceReview (every sentence its own turn); bulk -> BulkReview (one turn, all sentences).
User 2026-11-27: "a reviewer setting to say per sentence or bulk ... Gemma 4 and local llm suggestion for per
sentence, otherwise bulk"."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .review_conversation import ReviewConversation
from .types import ReviewPacket, Verdict

PER_SENTENCE = "per_sentence"
BULK = "bulk"
GRANULARITIES = (PER_SENTENCE, BULK)


class ReviewMethod(ABC):

    @abstractmethod
    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        """Raises ReviewerUnavailable (backend failed) or UnparseableVerdict (an answer was unreadable)."""
