"""NodeGuessScreen: the whole-node review (build log #60 (5)). Code lists the node's statements (title, each
sentence of the context summary, each line/sentence of every content item); ONE turn asks for every statement the
writer would have had to guess; any guess fails the node review with a reason per statement."""
from __future__ import annotations

from typing import Optional

from .node_screen_turns import SCREEN_MAX_TOKENS, Statement, read_guesses, screen_turn
from .review_conversation import ReviewConversation
from .review_method import ReviewMethod
from .sentence_splitter import SentenceSplitter
from .types import ReviewPacket, Verdict


class NodeGuessScreen(ReviewMethod):

    def __init__(self, splitter: Optional[SentenceSplitter] = None):
        self._splitter = splitter or SentenceSplitter()

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        statements = self._statements(packet)
        guesses = read_guesses(conversation.say(screen_turn(packet, statements), max_tokens=SCREEN_MAX_TOKENS),
                               len(statements))
        if not guesses:
            return Verdict(True, f"no guessed statements in {len(statements)}")
        return Verdict(False, "; ".join(f"statement {n} guessed ({statements[n - 1].shown()}): "
                                        f"{guesses[n] or 'not stated by any included reference'}"
                                        for n in sorted(guesses)))

    def _statements(self, packet: ReviewPacket) -> list[Statement]:
        statements = [Statement("title", packet.node_title.strip())] if packet.node_title.strip() else []
        statements += [Statement("context summary", s) for s in self._split(packet.node_context_summary)]
        for item in packet.content_items:
            source = " ".join((item.reference_id, *item.tags))
            statements += [Statement(source, s) for s in self._split(item.text)]
        return statements

    def _split(self, text: str) -> list[str]:
        return [sentence for line in text.splitlines() if line.strip() for sentence in self._splitter.split(line)]
