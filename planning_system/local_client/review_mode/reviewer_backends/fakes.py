"""FakeReviewerBackend: scripted model answers (text, or an exception to raise), prompts recorded."""
from __future__ import annotations

import json
from typing import Iterable, Union

from ..types import ReviewerUnavailable, Verdict
from .prompted_backend import PromptedReviewerBackend

Script = Union[str, Verdict, Exception]


def verdict_json(passed: bool, reason: str = "ok", suggested_title=None) -> str:
    return json.dumps({"passed": passed, "reason": reason, "suggested_title": suggested_title})


class FakeReviewerBackend(PromptedReviewerBackend):
    name = "fake"

    def __init__(self, replies: Iterable[Script] = ()):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def _ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.replies:
            raise ReviewerUnavailable("fake backend has no scripted reply left")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, Verdict):
            return verdict_json(reply.passed, reply.reason, reply.suggested_title)
        return reply
