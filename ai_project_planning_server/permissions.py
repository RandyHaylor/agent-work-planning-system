"""Generic role-and-scope permission rules.

This module knows nothing about HTTP or Postgres. It operates on plain values:
node ids, ancestor chains, a small Principal record, and a View record that the
caller fills from the database (which workorders and kbs the principal may read).
The caller supplies an ``ancestors(node_id)`` function returning [node, parent, ..., root].

Roles:
- admin: top-level. Not a token in the database but a user-approved session (token_id None).
  Reads and writes everything. Creates kbs, controls workorder visibility, resolves kb proposals,
  mints planners and workers.
- planner: the workorder's admin. Always scoped to the workorder node itself (a direct child of
  plans); no other scope exists for a planner. Full write inside the workorder, including other
  planners' docs and tokens: two planners on one workorder are two workorder admins. Read-only on
  every other workorder that is visible (or that explicitly grants its workorder visibility). Reads
  every kb. Decides which kbs its workorder's workers see (workorder-wide, or per node). Never writes
  a kb. Mints workers inside its workorder only.
- worker: reads its scope subtree, the kbs selected for it (nearest node override, else the
  workorder set), and ancestor environment docs (the API gathers those). Writes reports,
  escalations, spikes, kb proposals there, creates nodes beneath, edits only docs it authored.
- access: a caller holding only the server access token and no bearer. It may create a workorder
  (which mints that workorder's planner token) and nothing else.

Node ownership is a record, never a permission source.
"""
from dataclasses import dataclass
from typing import Callable, Optional

Ancestors = Callable[[int], list[int]]

ADMIN, PLANNER, WORKER, ACCESS = "admin", "planner", "worker", "access"
ROLES = frozenset({ADMIN, PLANNER, WORKER})
TOKEN_ROLES = frozenset({PLANNER, WORKER})  # roles a database token can carry; admin is a session only

PLANNER_ONLY_DOC_ROLES = frozenset({"summary", "instruction", "environment", "question", "survey", "approval", "review"})
WORKER_DOC_ROLES = frozenset({"report", "spike", "escalation", "kb_proposal"})
ALL_DOC_ROLES = PLANNER_ONLY_DOC_ROLES | WORKER_DOC_ROLES
ENV_ROLE = "environment"


@dataclass(frozen=True)
class Principal:
    token_id: Optional[int]  # None for the admin session and for an access-only caller
    scope_node_id: int
    role: str
    workorder_id: Optional[int] = None  # the workorder (direct child of plans) the scope lies in; None for admin


@dataclass(frozen=True)
class View:
    """What the principal may see. Filled by the caller from the database."""
    root: int
    plans: int
    kb: int
    readable_workorders: frozenset = frozenset()  # workorder node ids a planner may read (own + visible + granted)
    readable_kbs: frozenset = frozenset()       # kb node ids (direct children of kb) a worker may read


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


def workorder_of(node_id: int, ancestors: Ancestors, plans: int) -> Optional[int]:
    return _child_of(node_id, plans, ancestors)


def kb_of(node_id: int, ancestors: Ancestors, kb: int) -> Optional[int]:
    return _child_of(node_id, kb, ancestors)


def under_kb(node_id: int, ancestors: Ancestors, v: View) -> bool:
    return v.kb in ancestors(node_id)


def can_read(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    if p.role == ACCESS:
        return False
    if under_kb(node_id, ancestors, v):
        if p.role == PLANNER:
            return True  # planners read every kb; they choose what their workers see
        k = kb_of(node_id, ancestors, v.kb)
        return k is not None and k in v.readable_kbs
    if node_id in (v.root, v.plans):
        return p.role == PLANNER
    if p.role == PLANNER:
        proj = workorder_of(node_id, ancestors, v.plans)
        return proj is not None and proj in v.readable_workorders
    return in_subtree(node_id, p.scope_node_id, ancestors)


def _own_workorder(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    return p.workorder_id is not None and workorder_of(node_id, ancestors, v.plans) == p.workorder_id


def can_create_child(p: Principal, parent_id: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    if under_kb(parent_id, ancestors, v):
        return False
    if p.role == PLANNER:
        return _own_workorder(p, parent_id, ancestors, v)
    if p.role == WORKER:
        return in_subtree(parent_id, p.scope_node_id, ancestors) and workorder_of(parent_id, ancestors, v.plans) is not None
    return False


def can_create_workorder(p: Optional[Principal]) -> bool:
    """Anyone holding the server access token may start a workorder: no bearer, a planner, or the admin.
    A worker may not."""
    return p is None or p.role in (ADMIN, PLANNER, ACCESS)


def can_set_visibility(p: Principal) -> bool:
    return p.role == ADMIN


def can_assign_kbs(p: Principal, workorder_id: int) -> bool:
    """Which kbs a workorder's agents see is the planner's call (its own workorder), or the admin's."""
    return p.role == ADMIN or (p.role == PLANNER and p.workorder_id == workorder_id)


def can_set_state(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    return p.role == PLANNER and _own_workorder(p, node_id, ancestors, v)


def can_edit_node(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    """Rename, reparent, delete: the workorder's planner or the admin. Same rule as state."""
    return can_set_state(p, node_id, ancestors, v)


def can_write_doc(p: Principal, node_id: int, role: str, ancestors: Ancestors, v: View) -> bool:
    if role not in ALL_DOC_ROLES:
        return False
    if p.role == ADMIN:
        return True
    if under_kb(node_id, ancestors, v):
        return False
    if p.role == PLANNER:
        return _own_workorder(p, node_id, ancestors, v)
    if p.role == WORKER:
        return role in WORKER_DOC_ROLES and in_subtree(node_id, p.scope_node_id, ancestors)
    return False


def can_edit_doc(p: Principal, node_id: int, role: str, author: Optional[int], ancestors: Ancestors, v: View) -> bool:
    if p.role == ADMIN:
        return True
    if under_kb(node_id, ancestors, v):
        return False
    if p.role == PLANNER:
        return _own_workorder(p, node_id, ancestors, v)
    if p.role == WORKER:
        # A worker edits what it authored (its reports, and the summary of a node it created).
        return in_subtree(node_id, p.scope_node_id, ancestors) and author is not None and author == p.token_id
    return False


def can_answer_escalation(p: Principal, node_id: int, ancestors: Ancestors, v: View) -> bool:
    return p.role == ADMIN or (p.role == PLANNER and _own_workorder(p, node_id, ancestors, v))


def can_resolve_proposal(p: Principal) -> bool:
    """kb proposals are applied by the admin after a conversation with the user."""
    return p.role == ADMIN


def can_mint(p: Principal, scope_node_id: int, child_role: str, ancestors: Ancestors, v: View) -> bool:
    """Only planners and workers are minted; the admin is a session, never a token."""
    if child_role not in TOKEN_ROLES:
        return False
    proj = workorder_of(scope_node_id, ancestors, v.plans)
    if proj is None:
        return False  # planners and workers live inside a workorder
    if child_role == PLANNER and scope_node_id != proj:
        return False  # a planner is scoped to the workorder node itself, never a node inside it
    if p.role == ADMIN:
        return True
    if p.role == PLANNER:
        return child_role == WORKER and _own_workorder(p, scope_node_id, ancestors, v)
    return False


def planner_scope_ok(scope_node_id: int, ancestors: Ancestors, v: View) -> bool:
    """A planner token's scope must be a workorder node (a direct child of plans)."""
    return workorder_of(scope_node_id, ancestors, v.plans) == scope_node_id


def can_revoke(p: Principal, token_scope_node_id: int, ancestors: Ancestors, v: View) -> bool:
    """Admin anywhere; a planner for tokens inside its own workorder (lane-keeping)."""
    if p.role == ADMIN:
        return True
    return p.role == PLANNER and _own_workorder(p, token_scope_node_id, ancestors, v)


def can_rotate(p: Principal, token_id: int, token_role: str, token_scope_node_id: int, ancestors: Ancestors, v: View) -> bool:
    """Retrieve or reissue a token's plaintext. Admin: any token. A planner: any token in its own
    workorder, its own and other planners' included (a planner is the workorder's admin). Never outside
    its workorder. Workers: nothing."""
    if p.role == ADMIN:
        return True
    if p.role != PLANNER:
        return False
    return _own_workorder(p, token_scope_node_id, ancestors, v)


def can_list_tokens(p: Principal) -> bool:
    return p.role in (ADMIN, PLANNER)


def can_manage_workorders(p: Principal) -> bool:
    """Admin-only workorder management: creating kbs, visibility, visibility grants."""
    return p.role == ADMIN
