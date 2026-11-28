"""Permissions a command can require: plain data. RequestAuthorizer turns each into the facts
access/PermissionPolicy needs and asks it."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class Permission:
    """Base. Every permission except NoPrincipalNeeded requires an authenticated principal."""


@dataclass(frozen=True)
class NoPrincipalNeeded(Permission):
    """Only POST /admin/sessions: the password is checked by AdminSessions."""


@dataclass(frozen=True)
class Authenticated(Permission):
    """Any authenticated principal (e.g. GET /me, registering itself, loading into its own cache)."""


@dataclass(frozen=True)
class RoleIs(Permission):
    roles: tuple[str, ...]


@dataclass(frozen=True)
class CanReadNode(Permission):
    node_id: int


@dataclass(frozen=True)
class CanCreateNode(Permission):
    parent_id: int


@dataclass(frozen=True)
class CanEditNode(Permission):
    node_id: int


@dataclass(frozen=True)
class CanMoveNode(Permission):
    node_id: int
    new_parent_id: Optional[int]


@dataclass(frozen=True)
class CanSetState(Permission):
    node_id: int
    new_state: str


@dataclass(frozen=True)
class CanAssign(Permission):
    """can_assign on the node and can_mint a worker scoped to it."""
    node_id: int


@dataclass(frozen=True)
class CanCreateSupplementaryTask(Permission):
    task_id: int


@dataclass(frozen=True)
class CanAddContent(Permission):
    node_id: int


@dataclass(frozen=True)
class CanMint(Permission):
    role: str
    project_id: Optional[int]
    scope_node_id: Optional[int]


@dataclass(frozen=True)
class CanManageCredential(Permission):
    """Revoke / rotate. The issuer re-checks against the credential's own scope (it holds the row)."""
    credential_id: str


@dataclass(frozen=True)
class CanReadReaderItems(Permission):
    """Each id is a temp cache id (owner or admin) or a reference id (anyone who can read a citing node)."""
    reader_ids: tuple[str, ...]


@dataclass(frozen=True)
class CanReadReference(Permission):
    reference_id: str


@dataclass(frozen=True)
class CanRenderCitation(Permission):
    citation: str


@dataclass(frozen=True)
class CanSubmitUserQuote(Permission):
    """Quote key only."""


@dataclass(frozen=True)
class CanReviewProject(Permission):
    """List / take reviews in a project: admin, its planner, or the worker on its in-progress `review` task."""
    project_id: int


@dataclass(frozen=True)
class CanProposeSupersede(Permission):
    """Propose or list supersede candidates in a project: admin, or a planner/worker of the project."""
    project_id: int


@dataclass(frozen=True)
class CanDecideSupersede(Permission):
    """Confirm / reject one candidate: documents -> its project's planner or admin; user quotes -> admin."""
    candidate_id: str


@dataclass(frozen=True)
class CanReviewRecord(Permission):
    """CanReviewProject for the record's project (the ledger then checks the caller holds it)."""
    review_id: str
