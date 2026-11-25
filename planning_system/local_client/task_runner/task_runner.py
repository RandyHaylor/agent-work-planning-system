"""TaskRunner facade: launcher + registry. Level 6 scaffold: hollow."""
from __future__ import annotations

from .interface import RunningSessionsRegistryInterface, TaskRunnerInterface
from .task_session_launcher import TaskSessionLauncher
from .types import RunningSession, TaskStartRequest


class TaskRunner(TaskRunnerInterface):

    def __init__(self, launcher: TaskSessionLauncher, registry: RunningSessionsRegistryInterface):
        self._launcher = launcher
        self._registry = registry

    def start_task(self, request: TaskStartRequest) -> str:
        raise NotImplementedError("level 7")

    def stop_task(self, agent_id: str) -> None:
        raise NotImplementedError("level 7")

    def running_tasks(self) -> list[RunningSession]:
        raise NotImplementedError("level 7")
