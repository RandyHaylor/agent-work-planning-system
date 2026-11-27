"""OneShotModelCall: one prompt in, one answer out. No tools, no session."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import OneShotRequest, OneShotResponse


class OneShotModelCall(ABC):

    @abstractmethod
    def complete(self, request: OneShotRequest) -> OneShotResponse:
        """Raises ModelCallFailed when the model is unreachable or its answer has no text."""
