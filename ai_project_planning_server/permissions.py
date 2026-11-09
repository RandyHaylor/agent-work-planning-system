"""Generic role-and-scope permission rules.

This module knows nothing about HTTP or Postgres. It operates on plain values:
node ids, ancestor chains, a small Principal record, and a View record that the
caller fills from the database (which projects and kbs the principal may read).
The caller supplies an ``ancestors(node_id)`` function returning [node, parent, ..., root].

Three roles:
- admin: top-level. Not a token in the database but a user-approved session (token_id None).
  Reads and writes everything. Creates projects and kbs, assigns kbs to projects, controls
  project visibility, resolves kb proposals, mints planners and workers.
- planner: scoped to one project. Full write inside it. Read-only on every other project
  that is visible (or that explicitly grants its project visibility). Reads only the kbs
  assigned to its project. Never writes a kb. Mints workers inside its project only.
- worker: reads its scope subtree, the project's assigned kbs, and ancestor environment
  docs (the API gathers those). Writes reports, escalations, spikes, kb proposals there,
  creates nodes beneath, edits only docs it authored.

Node ownership is a record, never a permission source.
"""
from dataclasses import dataclass
from typing import Callable, Optional

Ancestors = Callable[[int], list[int]]

ADMIN, PLANNER, WORKER = "admin", "planner", "worker"
ROLES = frozenset({ADMIN, PLANNER, WORKER})
TOKEN_ROLES = frozenset({PLANNER, WORKER})  # roles a database token can carry; admin is a session only

PLANNER_ONLY_DOC_ROLES = frozenset({"summary", "instruction", "environment", "question", "survey", "approval", "review"})
WORKER_DOC_ROLES = frozenset({"report", "spike", "escalation", "kb_proposal"})
ALL_DOC_ROLES = PLANNER_ONLY_DOC_ROLES | WORKER_DOC_ROLES
ENV_ROLE = "environment"


@dataclass(frozen=True)
class Principal:
    token_id: Optional[int]  # None for the admin session
    scope_node_id: int
    role: str
    project_id: Optional[int] = None  # the project (direct child of plans) the scope lies in; None for admin


@dataclass(frozen=True)
class View:
    """What the principal may see. Filled by the caller from the database."""
    root: int
    plans: int
    kb: int
    readable_projects: frozenset = frozenset()  # project node ids a planner may read (own + visible + granted)
    readable_kbs: frozenset = frozenset()       # kb node ids (direct children of kb) assigned to the project


def in_subtree(node_id: int, root_id: int, ancestors: Ancestors) -> bool:
    """True if node_id is root_id or a descendant of it."""
    return root_id in ancestors(node_id)


def _child_of(node_id: int, container: int, ancestors: Ancestors) -> Optional[int]:
    """The direct child of ``container`` on node_id's chain, or None."""
    chain = ancestors(node_id)
    if container not in chain:
        return None
    i = chain.index(container)
    return chain[i - 1] if i > 0 else None


def project_of(node_id: int, ancestors: Ancestors, plans: int) -> Optional[int]:
    return _child_of(node_id, plans, ancestors)


def kb_of(node_id: int, ancestors: Ancestors, kb: int) -> Optional[int]:
    return _child_of(node_id, kb, ancestors)


def under_kb(node_id: int, ancestors: Ancestors, v: View) -> bool:
    return v.kb in ancestors(node_id)


def can_read(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    if under_kb(node_id, ancestors, v):
        k = kb_of(node_id, ancestors, v.kb)
        if k is None:  # the kb container itself
            return p.role == PLANNER
        return k in v.readable_kbs
    if node_id in (v.root, v.plans):
        return p.role == PLANNER
    if p.role == PLANNER:
        proj = project_of(node_id, ancestors, v.plans)
        return proj is not None and proj in v.readable_projects
    return in_subtree(node_id, p.scope_node_id, ancestors)


def _own_project(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    return p.project_id is not None and project_of(node_id, ancestors, v.plans) == p.project_id


def can_create_child(p: Principal, parent_id: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    if under_kb(parent_id, ancestors, v):
        return False
    if p.role == PLANNER:
        return _own_project(p, parent_id, ancestors, v)
    return in_subtree(parent_id, p.scope_node_id, ancestors) and project_of(parent_id, ancestors, v.plans) is not None


def can_set_state(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    return p.role == PLANNER and _own_project(p, node_id, ancestors, v)


def can_write_doc(p: Principal, node_id: int, role: str, ancestors: Ancestors, v: View) -> bool:
    if role not in ALL_DOC_ROLES:
        return False
    if p.role == ADMIN:
        return True
    if under_kb(node_id, ancestors, v):
        return False
    if p.role == PLANNER:
        return _own_project(p, node_id, ancestors, v)
    return role in WORKER_DOC_ROLES and in_subtree(node_id, p.scope_node_id, ancestors)


def can_edit_doc(p: Principal, node_id: int, role: str, author: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    if under_kb(node_id, ancestors, v):
        return False
    if p.role == PLANNER:
        return _own_project(p, node_id, ancestors, v)
    # A worker edits what it authored (its reports, and the summary of a node it created).
    return in_subtree(node_id, p.scope_node_id, ancestors) and author == p.token_id


def can_answer_escalation(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    return p.role == ADMIN or (p.role == PLANNER and _own_project(p, node_id, ancestors, v))


def can_resolve_proposal(p: Principal) -> bool:
    """kb proposals are applied by the admin after a conversation with the user."""
    return p.role == ADMIN


def can_mint(p: Principal, scope_node_id: int, child_role: str, ancestors: Ancestors, v: View) -> bool:
    """Only planners and workers are minted; the admin is a session, never a token."""
    if child_role not in TOKEN_ROLES:
        return False
    if p.role == ADMIN:
        # planners and workers live inside a project
        return project_of(scope_node_id, ancestors, v.plans) is not None
    if p.role == PLANNER:
        return child_role == WORKER and _own_project(p, scope_node_id, ancestors, v)
    return False


def can_revoke(p: Principal, token_scope_node_id: int, ancestors: Ancestors, v: View) -> bool:
    """Admin anywhere; a planner for tokens inside its own project (lane-keeping)."""
    if p.role == ADMIN:
        return True
    return p.role == PLANNER and _own_project(p, token_scope_node_id, ancestors, v)


def can_list_tokens(p: Principal) -> bool:
    return p.role in (ADMIN, PLANNER)


def can_manage_projects(p: Principal) -> bool:
    return p.role == ADMIN
