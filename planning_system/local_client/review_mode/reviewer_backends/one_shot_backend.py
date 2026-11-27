"""OneShotReviewerBackend: reviews through any OneShotModelCall (planning_system.model_calls). Selected as
`local_llm` (build log #47): by default the "local_gemma4" endpoint, the existing llama.cpp server."""
from __future__ import annotations

from planning_system.model_calls import ModelCallFailed, OneShotModelCall, OneShotRequest

from ..types import ReviewerUnavailable
from .prompted_backend import PromptedReviewerBackend

DEFAULT_REVIEW_MAX_TOKENS = 256


class OneShotReviewerBackend(PromptedReviewerBackend):
    name = "local_llm"

    def __init__(self, model_call: OneShotModelCall, max_tokens: int = DEFAULT_REVIEW_MAX_TOKENS):
        self._model_call, self._max_tokens = model_call, max_tokens

    def _ask(self, prompt: str) -> str:
        request = OneShotRequest(user_text=prompt, json_output=True, max_tokens=self._max_tokens, temperature=0.0)
        try:
            return self._model_call.complete(request).text
        except ModelCallFailed as error:
            raise ReviewerUnavailable(str(error)) from error
