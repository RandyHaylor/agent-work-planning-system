"""ReviewByKind: routes a packet to the method for what the review is about. Content packets go to the
configured granularity (per_sentence or bulk); whole-node packets to the guess screen (one call, build log
#60 (5)); supersede trials and quote checks to their one-call checks (05-spec-reference-supersede.md), whatever
the granularity."""
from __future__ import annotations

from typing import Optional

from .quote_check import QuoteCheck
from .review_conversation import ReviewConversation
from .review_method import ReviewMethod
from .trial_review import TrialReview
from .types import KIND_NODE, KIND_QUOTE_CHECK, KIND_TRIAL, ReviewPacket, Verdict


class ReviewByKind(ReviewMethod):

    def __init__(self, content_method: ReviewMethod, node_method: ReviewMethod,
                 trial_method: Optional[ReviewMethod] = None, quote_check_method: Optional[ReviewMethod] = None):
        self._content_method = content_method
        self._by_kind = {KIND_NODE: node_method, KIND_TRIAL: trial_method or TrialReview(),
                         KIND_QUOTE_CHECK: quote_check_method or QuoteCheck()}

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        return self._by_kind.get(packet.kind, self._content_method).run(packet, conversation)
