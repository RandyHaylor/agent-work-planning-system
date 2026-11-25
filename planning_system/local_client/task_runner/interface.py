"""Public interface of task_runner: start/stop task sessions for the planner. No planning logic."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import RunningSession, TaskStartRequest


class TaskRunnerInterface(ABC):

    @abstractmethod
    def start_task(self, request: TaskStartRequest) -> str:
        """Registers the agent, launches one headless session (token only in its environment; start prompt =
        role guidance + node context), records it, returns the session id without waiting."""

    @abstractmethod
    def stop_task(self, agent_id: str) -> None:
        """Terminates the session and marks it not alive. Never calls the server; node state is untouched."""

    @abstractmethod
    def running_tasks(self) -> list[RunningSession]: ...


class RunningSessionsRegistryInterface(ABC):
    """Local JSON file of sessions this client started."""

    @abstractmethod
    def record(self, session: RunningSession) -> None: ...

    @abstractmethod
    def mark_stopped(self, agent_id: str) -> None: ...

    @abstractmethod
    def all(self) -> list[RunningSession]: ...
