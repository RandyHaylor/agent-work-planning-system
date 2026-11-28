"""SentenceBySentenceReview: runs one review as a conversation and builds the verdict.
Every sentence is asked; any "yes" (unsupported claim) fails the review, naming the sentence. Requirement and
decision claims get one more turn after the sentences, the nothing-lost check (build log #60 (2))."""
from __future__ import annotations

from typing import Optional

from .review_conversation import ReviewConversation
from .review_method import ReviewMethod, verdict_from
from .review_turns import (needs_nothing_lost_check, nothing_lost_turn, opening_turn, read_sentence_answer,
                           read_title_answer, sentence_turn, title_turn)
from .sentence_splitter import SentenceSplitter
from .types import ReviewPacket, Verdict


class SentenceBySentenceReview(ReviewMethod):

    def __init__(self, splitter: Optional[SentenceSplitter] = None):
        self._splitter = splitter or SentenceSplitter()

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        sentences = self._splitter.split(packet.claim_text)
        if not sentences:
            return Verdict(False, "claim has no sentences to review")
        conversation.say(opening_turn(packet))
        answers = [read_sentence_answer(conversation.say(sentence_turn(number, len(sentences), sentence)))
                   for number, sentence in enumerate(sentences, start=1)]
        unsupported = {number: answer.reason for number, answer in enumerate(answers, start=1)
                       if answer.unsupported_claim}
        dropped = None
        if needs_nothing_lost_check(packet):
            lost = read_sentence_answer(conversation.say(nothing_lost_turn()))
            dropped = (lost.reason or "a condition was dropped or weakened",) if lost.unsupported_claim else ()
        suggested_title = read_title_answer(conversation.say(title_turn(packet.node_title)))
        return verdict_from(sentences, unsupported, dropped, suggested_title)
