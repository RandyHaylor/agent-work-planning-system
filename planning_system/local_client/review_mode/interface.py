"""Public interface of review_mode: the client loop that takes content reviews from the server, one at a time."""
from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Event
from typing import Optional


class ReviewModeInterface(ABC):

    @abstractmethod
    def run_once(self) -> Optional[str]:
        """Takes one pending review, runs the backend, submits the verdict. Returns the review id handled, or
        None when nothing is pending. Backend error or unparseable verdict: retry once, then release it."""

    @abstractmethod
    def serve(self, stop: Event) -> None:
        """Repeats run_once until `stop` is set; waits poll_seconds when the queue is empty. Finishes the review
        in hand before returning (graceful stop)."""
