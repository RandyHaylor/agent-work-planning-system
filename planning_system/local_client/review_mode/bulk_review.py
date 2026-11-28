"""BulkReview: one turn asks the per-sentence question of every numbered sentence at once (plus the title).
Code still splits the claim, so every sentence is named; any unsupported sentence fails the review."""
from __future__ import annotations

from typing import Optional

from .review_conversation import ReviewConversation
from .review_method import ReviewMethod
from .review_turns import bulk_turn, read_bulk_answer
from .sentence_splitter import SentenceSplitter
from .types import ReviewPacket, Verdict


class BulkReview(ReviewMethod):

    def __init__(self, splitter: Optional[SentenceSplitter] = None):
        self._splitter = splitter or SentenceSplitter()

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        sentences = self._splitter.split(packet.claim_text)
        if not sentences:
            return Verdict(False, "claim has no sentences to review")
        answer = read_bulk_answer(conversation.say(bulk_turn(packet, sentences)), len(sentences))
        failures = [f"sentence {number} unsupported: {answer.unsupported[number] or sentences[number - 1]}"
                    for number in sorted(answer.unsupported)]
        if failures:
            return Verdict(False, "; ".join(failures), answer.suggested_title)
        return Verdict(True, f"all {len(sentences)} sentences supported", answer.suggested_title)
