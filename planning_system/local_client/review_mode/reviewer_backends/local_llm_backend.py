"""local_llm (default): OpenAI-compatible POST to the local llama.cpp gemma4 server (build log #47).
The server has one slot shared with another team: calls are strictly sequential (one process-wide lock), and this
client never starts or stops that server."""
from __future__ import annotations

import threading
from typing import Optional

import httpx

from ..types import ReviewerUnavailable
from .prompted_backend import PromptedReviewerBackend

DEFAULT_LOCAL_LLM_URL = "http://127.0.0.1:8898/v1/chat/completions"
DEFAULT_LOCAL_LLM_MODEL = "gemma4-31b-jang-q3:latest"

_ONE_REQUEST_AT_A_TIME = threading.Lock()


class LocalLlmBackend(PromptedReviewerBackend):
    name = "local_llm"

    def __init__(self, url: str = DEFAULT_LOCAL_LLM_URL, model: str = DEFAULT_LOCAL_LLM_MODEL,
                 max_tokens: int = 256, timeout_seconds: float = 120.0,
                 transport: Optional[httpx.BaseTransport] = None):
        self._url, self._model, self._max_tokens = url, model, max_tokens
        self._timeout, self._transport = timeout_seconds, transport

    def _ask(self, prompt: str) -> str:
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }
        with _ONE_REQUEST_AT_A_TIME:
            try:
                with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                    response = client.post(self._url, json=body)
            except httpx.HTTPError as error:
                raise ReviewerUnavailable(f"local llm unreachable: {error}") from error
        if not response.is_success:
            raise ReviewerUnavailable(f"local llm returned {response.status_code}: {response.text[:200]}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ReviewerUnavailable(f"local llm answer has no message: {response.text[:200]}") from error
        return content if isinstance(content, str) else ""
