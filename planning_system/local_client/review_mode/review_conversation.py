"""ReviewConversation: one review's conversation with a model. Every turn sees the earlier turns of the same
review (user 2026-11-27: "one by one yes no but using the same session")."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ReviewConversation(ABC):

    @abstractmethod
    def say(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Sends the next turn and returns the model's answer. max_tokens: room for a longer answer than the
        backend's default (backends without a token limit ignore it). Raises ReviewerUnavailable on any backend
        failure."""
