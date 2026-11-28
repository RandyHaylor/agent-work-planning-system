"""Ports system_halt needs."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .types import Halt


class HaltStoragePort(ABC):
    """One row per halt in force; no row = not halted. Durable, so a restart keeps it."""

    @abstractmethod
    def all(self) -> list[Halt]: ...

    @abstractmethod
    def put(self, halt: Halt) -> None:
        """Insert or replace the halt for its scope (project_id, None = system)."""

    @abstractmethod
    def remove(self, project_id: Optional[int]) -> bool:
        """True when a halt was in force for that scope."""


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
