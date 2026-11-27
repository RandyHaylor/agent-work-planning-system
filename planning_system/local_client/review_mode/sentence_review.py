"""SentenceBySentenceReview: runs one review as a conversation and builds the verdict.
Every sentence is asked; any "yes" (unsupported claim) fails the review, naming the sentence."""
from __future__ import annotations

from typing import Optional

from .review_conversation import ReviewConversation
from .review_turns import (SentenceAnswer, opening_turn, read_sentence_answer, read_title_answer, sentence_turn,
                           title_turn)
from .sentence_splitter import SentenceSplitter
from .types import ReviewPacket, Verdict


class SentenceBySentenceReview:

    def __init__(self, splitter: Optional[SentenceSplitter] = None):
        self._splitter = splitter or SentenceSplitter()

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        sentences = self._splitter.split(packet.claim_text)
        if not sentences:
            return Verdict(False, "claim has no sentences to review")
        conversation.say(opening_turn(packet))
        answers = [read_sentence_answer(conversation.say(sentence_turn(number, len(sentences), sentence)))
                   for number, sentence in enumerate(sentences, start=1)]
        suggested_title = read_title_answer(conversation.say(title_turn(packet.node_title)))
        return self._verdict(sentences, answers, suggested_title)

    @staticmethod
    def _verdict(sentences: list[str], answers: list[SentenceAnswer], suggested_title: Optional[str]) -> Verdict:
        failures = [f"sentence {number} unsupported: {answer.reason or sentences[number - 1]}"
                    for number, answer in enumerate(answers, start=1) if answer.unsupported_claim]
        if failures:
            return Verdict(False, "; ".join(failures), suggested_title)
        return Verdict(True, f"all {len(sentences)} sentences supported", suggested_title)
