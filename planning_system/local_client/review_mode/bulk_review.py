"""BulkReview: one turn asks the per-sentence question of every numbered sentence at once (plus the title, and for
requirement/decision claims the nothing-lost check as an extra field, build log #60 (2)). Code still splits the
claim, so every sentence is named; any unsupported sentence or dropped condition fails the review."""
from __future__ import annotations

from typing import Optional

from .review_conversation import ReviewConversation
from .review_method import ReviewMethod, verdict_from
from .review_turns import bulk_turn, needs_nothing_lost_check, read_bulk_answer
from .sentence_splitter import SentenceSplitter
from .types import ReviewPacket, Verdict


class BulkReview(ReviewMethod):

    def __init__(self, splitter: Optional[SentenceSplitter] = None):
        self._splitter = splitter or SentenceSplitter()

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        sentences = self._splitter.split(packet.claim_text)
        if not sentences:
            return Verdict(False, "claim has no sentences to review")
        check = needs_nothing_lost_check(packet)
        answer = read_bulk_answer(conversation.say(bulk_turn(packet, sentences)), len(sentences), check)
        return verdict_from(sentences, answer.unsupported, answer.dropped_conditions if check else None,
                            answer.suggested_title)
