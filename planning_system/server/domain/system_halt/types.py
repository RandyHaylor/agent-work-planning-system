"""system_halt types: one halt (the whole system, or one project) and the current halt state."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional


@dataclass(frozen=True)
class Halt:
    project_id: Optional[int]        # None = the whole system
    halted_by: str
    reason: str
    halted_at: datetime


@dataclass(frozen=True)
class HaltState:
    system: Optional[Halt]
    projects: tuple[Halt, ...]

    @property
    def halted_project_ids(self) -> frozenset[int]:
        return frozenset(h.project_id for h in self.projects if h.project_id is not None)

    def blocks(self, project_ids: Iterable[Optional[int]]) -> Optional[Halt]:
        """The halt that refuses a write touching these projects (None entries = project unknown), or None."""
        if self.system is not None:
            return self.system
        for halt in self.projects:
            if halt.project_id in set(project_ids):
                return halt
        return None
