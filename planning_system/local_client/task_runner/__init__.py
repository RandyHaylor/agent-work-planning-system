"""task_runner: start/stop task sessions for the planner (specs: 05-spec-local-client.md, 05-spec-task-assignment.md).
Its registry is the one list of every process this client started (build log #68)."""
from .interface import RunningSessionsRegistryInterface, TaskRunnerInterface
from .running_sessions_registry import RunningSessionsRegistry
from .task_runner import TaskRunner
from .task_session_launcher import TaskSessionLauncher
from .types import (SESSION_KINDS, SESSION_REVIEW_LOOP, SESSION_REVIEWER, SESSION_TASK, TASK_ROLES, RunningSession,
                    TaskStartRequest)

__all__ = ["TaskRunner", "TaskRunnerInterface", "TaskSessionLauncher", "RunningSessionsRegistry",
           "RunningSessionsRegistryInterface", "RunningSession", "TaskStartRequest", "TASK_ROLES", "SESSION_KINDS",
           "SESSION_REVIEW_LOOP", "SESSION_REVIEWER", "SESSION_TASK"]
