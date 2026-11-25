"""local_llm (default): OpenAI-compatible POST to the local llama.cpp gemma4 server (build log #47)."""
from __future__ import annotations

from typing import Optional

import httpx

from .prompted_backend import PromptedReviewerBackend

DEFAULT_LOCAL_LLM_URL = "http://127.0.0.1:8898/v1/chat/completions"
DEFAULT_LOCAL_LLM_MODEL = "gemma4-31b-jang-q3:latest"


class LocalLlmBackend(PromptedReviewerBackend):
    name = "local_llm"

    def __init__(self, url: str = DEFAULT_LOCAL_LLM_URL, model: str = DEFAULT_LOCAL_LLM_MODEL,
                 max_tokens: int = 256, timeout_seconds: float = 120.0,
                 transport: Optional[httpx.BaseTransport] = None):
        self._url, self._model, self._max_tokens = url, model, max_tokens
        self._timeout, self._transport = timeout_seconds, transport

    def _ask(self, prompt: str) -> str:
        raise NotImplementedError
