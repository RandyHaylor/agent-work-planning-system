"""Supersede candidate commands (05-spec-reference-supersede.md, approved):
POST /supersede-candidates {project_id, old_reference_id, new_reference_id, reason}  ProposeSupersede
GET  /supersede-candidates?project_id=&status=                                       ListSupersedeCandidates
POST /supersede-candidates/{id}/confirm                                              ConfirmSupersede
POST /supersede-candidates/{id}/reject {reason}                                      RejectSupersede
Nothing supersedes automatically; confirm is the only path (documents: planner or admin; user quotes: admin)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal
from planning_system.server.domain.references import CANDIDATE_STATUSES, FOUND_PROPOSED, SupersedeCandidate

from .command import ReadCommand, WriteCommand
from .permissions import CanDecideSupersede, CanProposeSupersede, Permission
from .supersede_flow import open_candidate, reopen_citing_reviews


def _who(principal: Optional[Principal]) -> str:
    return (principal.agent_id or principal.role) if principal is not None else "server"


@dataclass(frozen=True)
class ConfirmedSupersede:
    candidate: SupersedeCandidate
    reopened_review_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProposeSupersede(WriteCommand):
    project_id: int
    old_reference_id: str
    new_reference_id: str
    reason: str = ""

    def required_permission(self) -> Permission:
        return CanProposeSupersede(self.project_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return open_candidate(services, self.project_id, self.old_reference_id, self.new_reference_id,
                              FOUND_PROPOSED, _who(principal), self.reason)


@dataclass(frozen=True)
class ListSupersedeCandidates(ReadCommand):
    project_id: int
    status: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status is not None and self.status not in CANDIDATE_STATUSES:
            raise Invalid(f"status must be one of {', '.join(CANDIDATE_STATUSES)}")

    def required_permission(self) -> Permission:
        return CanProposeSupersede(self.project_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.candidates.list(self.project_id, self.status)


@dataclass(frozen=True)
class ConfirmSupersede(WriteCommand):
    candidate_id: str

    def required_permission(self) -> Permission:
        return CanDecideSupersede(self.candidate_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        candidate = services.candidates.confirm(self.candidate_id, _who(principal))
        reopened = reopen_citing_reviews(services, candidate)
        return ConfirmedSupersede(candidate, tuple(r.id for r in reopened))


@dataclass(frozen=True)
class RejectSupersede(WriteCommand):
    candidate_id: str
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise Invalid("say why it is not a supersede (--reason)")

    def required_permission(self) -> Permission:
        return CanDecideSupersede(self.candidate_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.candidates.reject(self.candidate_id, _who(principal), self.reason)
