"""OneShotReviewerBackend: reviews through any ChatModelCall (planning_system.model_calls), one chat history per
review. Selected as `local_llm` (build log #47): by default the "local_gemma4" endpoint, the existing llama.cpp
server. (Name kept from the one-shot reviewer it replaced, build log #55.)"""
from __future__ import annotations

from planning_system.model_calls import ChatModelCall

from ..review_conversation import ReviewConversation
from .conversational_backend import ConversationalReviewerBackend
from .conversations import ChatHistoryConversation

DEFAULT_REVIEW_MAX_TOKENS = 256         # per turn: one short JSON answer


class OneShotReviewerBackend(ConversationalReviewerBackend):
    name = "local_llm"

    def __init__(self, model_call: ChatModelCall, max_tokens: int = DEFAULT_REVIEW_MAX_TOKENS):
        self._model_call, self._max_tokens = model_call, max_tokens

    def _open_conversation(self) -> ReviewConversation:
        return ChatHistoryConversation(self._model_call, self._max_tokens)
