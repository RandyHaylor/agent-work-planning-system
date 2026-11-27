"""types: request/response values for one-shot and multi-turn chat calls, and the one error every model call
raises."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional


@dataclass(frozen=True)
class OneShotRequest:
    user_text: str
    system_text: Optional[str] = None
    json_output: bool = False
    max_tokens: int = 256
    temperature: float = 0.0


@dataclass(frozen=True)
class ChatMessage:
    role: str                  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class ChatRequest:
    """The whole conversation so far; the model answers the last user message."""
    messages: tuple[ChatMessage, ...]
    json_output: bool = False
    max_tokens: int = 256
    temperature: float = 0.0

    @classmethod
    def from_one_shot(cls, request: OneShotRequest) -> "ChatRequest":
        messages = ((ChatMessage("system", request.system_text),) if request.system_text else ()) \
            + (ChatMessage("user", request.user_text),)
        return cls(messages, request.json_output, request.max_tokens, request.temperature)


@dataclass(frozen=True)
class OneShotResponse:
    text: str
    model: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)


class ModelCallFailed(Exception):
    """The model could not be reached or gave no usable answer."""
