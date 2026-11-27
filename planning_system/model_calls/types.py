"""types: the one-shot request/response values and the one error every model call raises."""
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
class OneShotResponse:
    text: str
    model: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)


class ModelCallFailed(Exception):
    """The model could not be reached or gave no usable answer."""
