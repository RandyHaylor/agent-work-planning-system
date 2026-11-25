"""task_runner types (specs: 05-spec-task-assignment.md, 05-spec-local-client.md)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TASK_ROLES = ("worker", "planner")   # "planner" = a dev manager for a very large task


@dataclass(frozen=True)
class TaskStartRequest:
    node_id: int
    agent_id: str                     # also the Claude session id (one id, registry key)
    role: str                         # "worker" | "planner"
    token: str = field(repr=False)    # goes only into the session's environment, never into the prompt
    working_directory: Path = Path(".")
    allowed_tools: tuple[str, ...] = ()


@dataclass
class RunningSession:
    """One row of the local running-sessions registry."""
    agent_id: str
    node_id: int
    role: str
    working_directory: str
    pid: Optional[int] = None
    alive: bool = True
