"""task_assignment (server part): assign a task node and mint the worker's scoped token in one transaction.

Public surface: import from this package, not its files. `fakes` stays a separate
test-support submodule."""
from .interface import TaskAssigner
from .task_assigner import TaskAssignerService
from .types import Assignment

__all__ = ["Assignment", "TaskAssigner", "TaskAssignerService"]
