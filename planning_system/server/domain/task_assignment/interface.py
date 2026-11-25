"""Public interface of task_assignment (spec: 05-spec-task-assignment.md): assign + mint, nothing else.
The server never starts or stops processes."""
from abc import ABC, abstractmethod

from planning_system.contract import Principal

from .types import Assignment


class TaskAssigner(ABC):
    @abstractmethod
    def assign(self, issuer: Principal, node_id: int, agent_id: str, branch: str) -> Assignment:
        """Sets assignee, branch and state "assigned" and mints a worker token scoped to the node.
        Invalid for a node with children or a done/abandoned node; Forbidden when the issuer may
        not mint. Runs inside the caller's transaction, so a failed mint leaves the node unchanged."""
