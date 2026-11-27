"""ReviewConversation: one review's conversation with a model. Every turn sees the earlier turns of the same
review (user 2026-11-27: "one by one yes no but using the same session")."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ReviewConversation(ABC):

    @abstractmethod
    def say(self, text: str) -> str:
        """Sends the next turn and returns the model's answer. Raises ReviewerUnavailable on any backend failure."""
