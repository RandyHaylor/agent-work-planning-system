"""FakeOneShotModelCall: scripted answers for tests; records every request (one-shot or chat)."""
from __future__ import annotations

from typing import Iterable, Union

from .interface import ChatModelCall
from .types import ChatRequest, ModelCallFailed, OneShotRequest, OneShotResponse


class FakeOneShotModelCall(ChatModelCall):
    """Each scripted answer is the reply text, or an exception to raise. Raises ModelCallFailed when out of answers.
    `requests` holds what the caller sent: OneShotRequest from complete(), ChatRequest from chat()."""

    def __init__(self, answers: Iterable[Union[str, Exception]], model: str = "fake-model"):
        self._answers = list(answers)
        self.model = model
        self.requests: list[Union[OneShotRequest, ChatRequest]] = []

    def complete(self, request: OneShotRequest) -> OneShotResponse:
        self.requests.append(request)
        return self._next_answer()

    def chat(self, request: ChatRequest) -> OneShotResponse:
        self.requests.append(request)
        return self._next_answer()

    def _next_answer(self) -> OneShotResponse:
        if not self._answers:
            raise ModelCallFailed("fake model call has no scripted answer left")
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return OneShotResponse(text=answer, model=self.model, usage={})
