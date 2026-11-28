"""TaskRunner facade: launcher + registry."""
from __future__ import annotations

import os
import signal
from typing import Callable, Optional

from ..harness_adapters import PersistentReviewerSessionHandle
from .interface import RunningSessionsRegistryInterface, TaskRunnerInterface
from .task_session_launcher import TaskSessionLauncher
from .types import RunningSession, TaskStartRequest


class TaskRunner(TaskRunnerInterface):

    def __init__(self, launcher: TaskSessionLauncher, registry: RunningSessionsRegistryInterface,
                 launch_guard: Optional[Callable[[], None]] = None):
        """launch_guard: raises to refuse a start (a halted client, build log #68)."""
        self._launcher = launcher
        self._registry = registry
        self._launch_guard = launch_guard or (lambda: None)
        self._handles: dict[str, PersistentReviewerSessionHandle] = {}

    def start_task(self, request: TaskStartRequest) -> str:
        self._launch_guard()
        handle = self._launcher.launch(request)
        self._handles[request.agent_id] = handle
        self._registry.record(RunningSession(request.agent_id, request.node_id, request.role,
                                             str(request.working_directory), getattr(handle, "pid", None)))
        return handle.session_id

    def stop_task(self, agent_id: str) -> None:
        """Terminates by handle when this process started it, otherwise by the recorded pid (a later
        `planning task stop` runs in a new process). Never calls the server."""
        handle = self._handles.pop(agent_id, None)
        if handle is not None:
            handle.terminate()
        else:
            self._kill_recorded_process(agent_id)
        self._registry.mark_stopped(agent_id)

    def running_tasks(self) -> list[RunningSession]:
        return self._registry.all()

    def _kill_recorded_process(self, agent_id: str) -> None:
        pid = next((s.pid for s in self._registry.all() if s.agent_id == agent_id), None)
        if pid is None:
            return
        try:
            os.killpg(pid, signal.SIGTERM)    # headless sessions run in their own process group
        except (ProcessLookupError, PermissionError):
            pass
        except (OSError, AttributeError):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
