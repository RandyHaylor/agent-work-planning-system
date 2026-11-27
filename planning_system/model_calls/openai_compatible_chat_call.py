"""OpenAiCompatibleChatCall: one POST to an OpenAI-compatible /chat/completions endpoint (e.g. llama.cpp server).

max_concurrency limits calls in flight per base_url across the whole process (default 1: a shared server with one
slot). This class never starts or stops a server."""
from __future__ import annotations

import threading
from typing import Mapping, Optional

import httpx

from .interface import OneShotModelCall
from .types import ModelCallFailed, OneShotRequest, OneShotResponse

_LIMITS: dict[tuple[str, int], threading.Semaphore] = {}
_LIMITS_LOCK = threading.Lock()


def _limit_for(base_url: str, max_concurrency: int) -> threading.Semaphore:
    with _LIMITS_LOCK:
        key = (base_url, max_concurrency)
        if key not in _LIMITS:
            _LIMITS[key] = threading.Semaphore(max_concurrency)
        return _LIMITS[key]


class OpenAiCompatibleChatCall(OneShotModelCall):

    def __init__(self, base_url: str, model: str, extra_body: Optional[Mapping] = None,
                 timeout_seconds: float = 120.0, max_concurrency: int = 1,
                 transport: Optional[httpx.BaseTransport] = None):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._extra_body = dict(extra_body or {})
        self._timeout, self._transport = timeout_seconds, transport
        self._limit = _limit_for(self.base_url, max_concurrency)

    @property
    def url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def complete(self, request: OneShotRequest) -> OneShotResponse:
        with self._limit:
            try:
                with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                    response = client.post(self.url, json=self._body(request))
            except httpx.HTTPError as error:
                raise ModelCallFailed(f"model endpoint {self.base_url} unreachable: {error}") from error
        if not response.is_success:
            raise ModelCallFailed(f"model endpoint returned {response.status_code}: {response.text[:200]}")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ModelCallFailed(f"model answer has no message: {response.text[:200]}") from error
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return OneShotResponse(text=content if isinstance(content, str) else "",
                               model=str(payload.get("model") or self.model),
                               usage={k: v for k, v in usage.items() if isinstance(v, int)})

    def _body(self, request: OneShotRequest) -> dict:
        messages = []
        if request.system_text:
            messages.append({"role": "system", "content": request.system_text})
        messages.append({"role": "user", "content": request.user_text})
        body = {**self._extra_body, "model": self.model, "messages": messages,
                "temperature": request.temperature, "max_tokens": request.max_tokens, "stream": False}
        if request.json_output:
            body["response_format"] = {"type": "json_object"}
        return body
