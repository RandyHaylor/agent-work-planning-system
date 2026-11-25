"""Public interface of review_worker: "a simple call" to ask a persistent reviewer session a question."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence


class ReviewWorkerInterface(ABC):

    @abstractmethod
    def ask(self, question: str, context_paths: Sequence[Path] = ()) -> str:
        """Sends the question to one persistent headless reviewer session and returns its answer.
        Reuses the session; on a context-exhaustion response rotates to a fresh session and retries once."""
