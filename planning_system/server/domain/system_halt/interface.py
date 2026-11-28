"""Public interface of system_halt: the admin's stop switch (build log #68). While the system, or a project, is
halted every write command and every review hand-out is refused with Halted (423); reads still work."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional

from .types import HaltState


class HaltSwitch(ABC):

    @abstractmethod
    def state(self) -> HaltState: ...

    @abstractmethod
    def halt(self, project_id: Optional[int], halted_by: str, reason: str = "") -> HaltState:
        """project_id None = the whole system. Halting again replaces the earlier halt's reason."""

    @abstractmethod
    def unhalt(self, project_id: Optional[int]) -> HaltState:
        """Lifts that scope's halt (no error when it was not halted)."""

    @abstractmethod
    def ensure_writable(self, project_ids: Iterable[Optional[int]]) -> None:
        """Raises Halted when the system, or one of these projects, is halted."""
