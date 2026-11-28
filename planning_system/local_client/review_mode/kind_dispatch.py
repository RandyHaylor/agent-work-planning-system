"""ReviewByKind: routes a packet to the method for what the review is about. Content packets go to the
configured granularity (per_sentence or bulk); whole-node packets to the guess screen (one call, build log
#60 (5)), whatever the granularity."""
from __future__ import annotations

from .review_conversation import ReviewConversation
from .review_method import ReviewMethod
from .types import KIND_NODE, ReviewPacket, Verdict


class ReviewByKind(ReviewMethod):

    def __init__(self, content_method: ReviewMethod, node_method: ReviewMethod):
        self._content_method, self._node_method = content_method, node_method

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        method = self._node_method if packet.kind == KIND_NODE else self._content_method
        return method.run(packet, conversation)
