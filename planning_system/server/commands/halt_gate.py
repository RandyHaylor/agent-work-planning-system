"""halt_gate: the one place the admin's halt is enforced (build log #68). CommandRunner asks it before every command:
reads always pass; a write (every review hand-out is a write: TakeReview) is refused with Halted while the system,
or the project the write touches, is halted. Commands that must work while halted (admin log-in/out, halt and
un-halt) set allowed_while_halted.

The project a write touches: the caller's own project (planner/worker tokens are project-scoped) and the project the
command's permission names or resolves to (a node's project, a review's, a candidate's). A write with no project
(e.g. creating a project, storing a user exchange) is refused only by a whole-system halt."""
from __future__ import annotations

from typing import Callable, Optional

from planning_system.contract import Principal
from planning_system.errors import DomainError

from . import permissions as P
from .command import Access, Command
from .request_authorizer import TreeFacts
from .services import Services

_NODE_FIELD = {P.CanCreateNode: "parent_id", P.CanEditNode: "node_id", P.CanMoveNode: "node_id",
               P.CanSetState: "node_id", P.CanAssign: "node_id", P.CanCreateSupplementaryTask: "task_id",
               P.CanAddContent: "node_id"}


class HaltGate:

    def check(self, command: Command, principal: Optional[Principal], services: Services) -> None:
        """Raises Halted."""
        if command.access is Access.READ or command.allowed_while_halted or services.halt is None:
            return
        services.halt.ensure_writable({principal.project_id if principal else None,
                                       self._project_of(command.required_permission(), services)})

    @staticmethod
    def _project_of(permission: P.Permission, services: Services) -> Optional[int]:
        resolvers: dict[type, Callable[[], Optional[int]]] = {
            P.CanMint: lambda: permission.project_id,
            P.CanReviewProject: lambda: permission.project_id,
            P.CanProposeSupersede: lambda: permission.project_id,
            P.CanReviewRecord: lambda: services.reviews.get(permission.review_id).project_id,
            P.CanDecideSupersede: lambda: services.candidates.get(permission.candidate_id).project_id,
        }
        node_field = _NODE_FIELD.get(type(permission))
        if node_field is not None:
            resolvers[type(permission)] = lambda: TreeFacts(services).of(getattr(permission, node_field)).project_id
        resolver = resolvers.get(type(permission))
        if resolver is None:
            return None
        try:
            return resolver()
        except DomainError:          # the command itself reports a missing node/review
            return None
