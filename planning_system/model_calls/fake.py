"""FakeOneShotModelCall: scripted answers for tests; records every request."""
from __future__ import annotations

from typing import Iterable, Union

from .interface import OneShotModelCall
from .types import ModelCallFailed, OneShotRequest, OneShotResponse


class FakeOneShotModelCall(OneShotModelCall):
    """Each scripted answer is the reply text, or an exception to raise. Raises ModelCallFailed when out of answers."""

    def __init__(self, answers: Iterable[Union[str, Exception]], model: str = "fake-model"):
        self._answers = list(answers)
        self.model = model
        self.requests: list[OneShotRequest] = []

    def complete(self, request: OneShotRequest) -> OneShotResponse:
        self.requests.append(request)
        if not self._answers:
            raise ModelCallFailed("fake model call has no scripted answer left")
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return OneShotResponse(text=answer, model=self.model, usage={})
