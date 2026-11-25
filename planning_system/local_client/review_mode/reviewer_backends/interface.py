"""ReviewerBackend: strategy for asking one model/harness to review one packet."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import ReviewPacket, Verdict


class ReviewerBackend(ABC):
    name: str = ""

    @abstractmethod
    def review(self, packet: ReviewPacket) -> Verdict:
        """Raises ReviewerUnavailable (backend failed) or UnparseableVerdict (answer was not the JSON verdict)."""
