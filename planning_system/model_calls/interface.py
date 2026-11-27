"""OneShotModelCall: one prompt in, one answer out. ChatModelCall: also answers a whole conversation (the caller
keeps the history). No tools in either."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import ChatRequest, OneShotRequest, OneShotResponse


class OneShotModelCall(ABC):

    @abstractmethod
    def complete(self, request: OneShotRequest) -> OneShotResponse:
        """Raises ModelCallFailed when the model is unreachable or its answer has no text."""


class ChatModelCall(OneShotModelCall):

    @abstractmethod
    def chat(self, request: ChatRequest) -> OneShotResponse:
        """Answers the last user message given every earlier message. Raises ModelCallFailed like complete()."""

    def complete(self, request: OneShotRequest) -> OneShotResponse:
        return self.chat(ChatRequest.from_one_shot(request))
