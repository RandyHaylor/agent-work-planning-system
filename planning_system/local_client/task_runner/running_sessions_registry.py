"""running_sessions_registry: local JSON file of sessions this client started. Level 6 scaffold: hollow."""
from __future__ import annotations

from pathlib import Path

from .interface import RunningSessionsRegistryInterface
from .types import RunningSession


class RunningSessionsRegistry(RunningSessionsRegistryInterface):

    def __init__(self, registry_file: Path):
        self._registry_file = registry_file

    def record(self, session: RunningSession) -> None:
        raise NotImplementedError("level 7")

    def mark_stopped(self, agent_id: str) -> None:
        raise NotImplementedError("level 7")

    def all(self) -> list[RunningSession]:
        raise NotImplementedError("level 7")
