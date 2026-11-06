"""Generic role-and-scope permission rules.

This module knows nothing about HTTP or Postgres. It operates on plain values:
node ids, ancestor chains, and a small Principal record. The caller supplies an
``ancestors(node_id)`` function returning the chain [node, parent, ..., root].

Two roles:
- planner: full rights on every node in its scope subtree. Reads ancestors too.
  Any planner may write anywhere in the ``kb`` subtree.
- worker: reads only its scope node and descendants. Writes only reports,
  escalations, spikes, kb proposals there, and creates nodes beneath.
  Sees ancestor docs of role ``environment`` only (see ``sees_env_doc``).

Node ownership is a record, never a permission source.
"""
from dataclasses import dataclass
from typing import Callable, Optional

Ancestors = Callable[[int], list[int]]

PLANNER, WORKER = "planner", "worker"
ROLES = frozenset({PLANNER, WORKER})

PLANNER_ONLY_DOC_ROLES = frozenset({"summary", "instruction", "environment", "question", "survey", "approval", "review"})
WORKER_DOC_ROLES = frozenset({"report", "spike", "escalation", "kb_proposal"})
ENV_ROLE = "environment"


@dataclass(frozen=True)
class Principal:
    token_id: int
    scope_node_id: int
    role: str
    is_root: bool = False


def in_subtree(node_id: int, root_id: int, ancestors: Ancestors) -> bool:
    """True if node_id is root_id or a descendant of it."""
    return root_id in ancestors(node_id)


def is_kb(node_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    return kb_root is not None and kb_root in ancestors(node_id)


def can_read(p: Principal, node_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if in_subtree(node_id, p.scope_node_id, ancestors):
        return True
    if is_kb(node_id, ancestors, kb_root):
        return True
    if p.role == PLANNER and node_id in ancestors(p.scope_node_id):
        return True
    return False


def sees_env_doc(p: Principal, doc_node_id: int, ancestors: Ancestors) -> bool:
    """A worker may see an ``environment`` doc on any ancestor of its scope.
    (Planners read ancestors fully via ``can_read``.)"""
    return doc_node_id in ancestors(p.scope_node_id)


def can_create_child(p: Principal, parent_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(parent_id, ancestors, kb_root):
        return p.role == PLANNER
    return in_subtree(parent_id, p.scope_node_id, ancestors)


def can_set_state(p: Principal, node_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(node_id, ancestors, kb_root):
        return p.role == PLANNER
    return p.role == PLANNER and in_subtree(node_id, p.scope_node_id, ancestors)


def can_write_doc(p: Principal, node_id: int, role: str, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    """kb is writable by any planner (workers read-only); elsewhere scope applies."""
    if is_kb(node_id, ancestors, kb_root):
        return p.role == PLANNER and role in PLANNER_ONLY_DOC_ROLES | WORKER_DOC_ROLES
    if not in_subtree(node_id, p.scope_node_id, ancestors):
        return False
    if p.role == PLANNER:
        return role in PLANNER_ONLY_DOC_ROLES or role in WORKER_DOC_ROLES
    return role in WORKER_DOC_ROLES


def can_edit_doc(p: Principal, node_id: int, role: str, author: int,
                 ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(node_id, ancestors, kb_root):
        return p.role == PLANNER
    if not in_subtree(node_id, p.scope_node_id, ancestors):
        return False
    if p.role == PLANNER:
        return True
    return author == p.token_id and role in WORKER_DOC_ROLES


def can_answer_escalation(p: Principal, node_id: int, ancestors: Ancestors) -> bool:
    return p.role == PLANNER and in_subtree(node_id, p.scope_node_id, ancestors)


def can_mint(p: Principal, scope_node_id: int, child_role: str, ancestors: Ancestors) -> bool:
    if p.role != PLANNER or child_role not in ROLES:
        return False
    return in_subtree(scope_node_id, p.scope_node_id, ancestors)


def can_revoke(p: Principal, token_scope_node_id: int, ancestors: Ancestors) -> bool:
    """Any planner whose scope contains the token's scope may revoke it (lane-keeping)."""
    return p.role == PLANNER and in_subtree(token_scope_node_id, p.scope_node_id, ancestors)


def can_list_tokens(p: Principal) -> bool:
    return p.role == PLANNER
