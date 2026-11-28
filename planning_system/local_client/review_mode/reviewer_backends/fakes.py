"""FakeReviewerBackend: one scripted reply per review (text parsed as a verdict, a Verdict, or an exception to
raise); records the opening turn each review would send. For review-loop tests; backends' turn-by-turn behaviour
is tested against the real backends with fake transports."""
from __future__ import annotations

import json
from typing import Iterable, Union

from ..review_turns import opening_turn
from ..types import ReviewerUnavailable, ReviewPacket, Verdict
from ..verdict_parser import parse_verdict
from .interface import ReviewerBackend

Script = Union[str, Verdict, Exception]


def verdict_json(passed: bool, reason: str = "ok", suggested_title=None) -> str:
    return json.dumps({"passed": passed, "reason": reason, "suggested_title": suggested_title})


def turn_reply(unsupported_claim: bool = False, reason: str = "", suggested_title=None) -> str:
    """One JSON object every review turn accepts (opening, each sentence, title, bulk): handy for fake transports.
    In bulk, unsupported_claim marks sentence 1 only."""
    return json.dumps({"ready": True, "answer": "yes" if unsupported_claim else "no", "reason": reason,
                       "suggested_title": suggested_title, "dropped_conditions": [],
                       "unsupported": [{"sentence": 1, "reason": reason}] if unsupported_claim else []})


class FakeReviewerBackend(ReviewerBackend):
    name = "fake"

    def __init__(self, replies: Iterable[Script] = ()):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def review(self, packet: ReviewPacket) -> Verdict:
        reply = self._ask(opening_turn(packet))
        return reply if isinstance(reply, Verdict) else parse_verdict(reply)

    def _ask(self, prompt: str):
        self.prompts.append(prompt)
        if not self.replies:
            raise ReviewerUnavailable("fake backend has no scripted reply left")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
