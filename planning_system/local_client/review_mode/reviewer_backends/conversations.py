"""ReviewConversation adapters, one per way a backend can hold a session:
- ChatHistoryConversation: a ChatModelCall; the full message history is sent each turn (llama.cpp reuses its
  prompt cache for the shared prefix).
- ReviewWorkerConversation: the persistent `claude -p` reviewer session (the harness keeps the history).
- TranscriptReplayConversation: any one-shot ask (e.g. parked pi); earlier turns are replayed inside each prompt."""
from __future__ import annotations

from typing import Callable

from planning_system.model_calls import ChatMessage, ChatModelCall, ChatRequest, ModelCallFailed

from ...review_worker import ReviewWorkerInterface
from ..review_conversation import ReviewConversation
from ..types import ReviewerUnavailable


class ChatHistoryConversation(ReviewConversation):

    def __init__(self, model_call: ChatModelCall, max_tokens: int):
        self._model_call, self._max_tokens = model_call, max_tokens
        self._messages: list[ChatMessage] = []

    def say(self, text: str) -> str:
        self._messages.append(ChatMessage("user", text))
        request = ChatRequest(tuple(self._messages), json_output=True, max_tokens=self._max_tokens, temperature=0.0)
        try:
            answer = self._model_call.chat(request).text
        except ModelCallFailed as error:
            raise ReviewerUnavailable(str(error)) from error
        self._messages.append(ChatMessage("assistant", answer))
        return answer


class ReviewWorkerConversation(ReviewConversation):

    def __init__(self, review_worker: ReviewWorkerInterface):
        self._review_worker = review_worker

    def say(self, text: str) -> str:
        try:
            return self._review_worker.ask(text)
        except Exception as error:           # any harness failure (timeout, dead process) = backend unavailable
            raise ReviewerUnavailable(f"claude reviewer failed: {error}") from error


class TranscriptReplayConversation(ReviewConversation):

    def __init__(self, ask: Callable[[str], str]):
        self._ask = ask
        self._turns: list[tuple[str, str]] = []

    def say(self, text: str) -> str:
        answer = self._ask(self._prompt(text))
        self._turns.append((text, answer))
        return answer

    def _prompt(self, text: str) -> str:
        if not self._turns:
            return text
        earlier = "\n\n".join(f"YOU WERE TOLD:\n{told}\nYOU ANSWERED:\n{answered}" for told, answered in self._turns)
        return f"EARLIER IN THIS REVIEW:\n{earlier}\n\nNOW:\n{text}"
