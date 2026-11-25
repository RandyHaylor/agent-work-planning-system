"""POST /projects: ProjectTree.create(None, ..., level "what we're doing"). Admin only: the policy
has no rule for parentless nodes, and a planner token is scoped to an existing project."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal

from .command import WriteCommand
from .permissions import RoleIs, Permission

PROJECT_LEVEL = "what we're doing"


@dataclass(frozen=True)
class CreateProject(WriteCommand):
    title: str
    context_summary: str

    def required_permission(self) -> Permission:
        return RoleIs(("admin",))

    def run(self, services, principal: Optional[Principal]) -> Any:
        services.enforcement.check_title(self.title)
        return services.tree.create(None, self.title, PROJECT_LEVEL, self.context_summary)
