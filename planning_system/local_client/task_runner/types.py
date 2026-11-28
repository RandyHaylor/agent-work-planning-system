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
    model: Optional[str] = None       # e.g. "haiku"; None = the harness default


SESSION_TASK = "task"               # a headless task session (`planning task start`)
SESSION_REVIEW_LOOP = "review_loop"  # a `planning review serve` process
SESSION_REVIEWER = "reviewer"       # one reviewer model process (`claude -p` turn) started by a review loop
SESSION_KINDS = (SESSION_TASK, SESSION_REVIEW_LOOP, SESSION_REVIEWER)


@dataclass
class RunningSession:
    """One row of the local running-sessions registry: every process this client started (build log #68).
    agent_id is the row key (task: the agent id; others: "<kind>-<pid>"). node_id: the task node; for a review loop
    the project it reviews; 0 for a reviewer process. process_group: pid leads its own process group (kill the
    group); False = kill only that pid (a review loop runs in the caller's group)."""
    agent_id: str
    node_id: int
    role: str
    working_directory: str
    pid: Optional[int] = None
    alive: bool = True
    kind: str = SESSION_TASK
    process_group: bool = True
