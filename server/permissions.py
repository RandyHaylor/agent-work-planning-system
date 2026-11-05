"""Generic scope-tree permission rules.

This module knows nothing about HTTP or Postgres. It operates on plain values:
node ids, ancestor chains, and a small Principal record. The caller supplies an
``ancestors(node_id)`` function returning the chain [node, parent, ..., root].
"""
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

Ancestors = Callable[[int], list[int]]

OWNER_ONLY_ROLES = frozenset({"summary", "instruction", "question"})
HOLDER_ROLES = frozenset({"report", "spike", "escalation", "kb_proposal"})


@dataclass(frozen=True)
class Principal:
    token_id: int
    scope_node_id: int
    can_spawn: bool
    is_root: bool = False


def in_subtree(node_id: int, root_id: int, ancestors: Ancestors) -> bool:
    """True if node_id is root_id or a descendant of it."""
    return root_id in ancestors(node_id)


def can_read(p: Principal, node_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    chain = ancestors(node_id)
    if p.scope_node_id in chain:
        return True
    if node_id in ancestors(p.scope_node_id):
        return True
    if kb_root is not None and kb_root in chain:
        return True
    return False


def is_kb(node_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    return kb_root is not None and kb_root in ancestors(node_id)


def can_create_child(p: Principal, parent_id: int, ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(parent_id, ancestors, kb_root):
        return p.is_root
    return in_subtree(parent_id, p.scope_node_id, ancestors)


def can_set_state(p: Principal, node_id: int, node_owner: Optional[int], parent_owner: Optional[int],
                  ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(node_id, ancestors, kb_root):
        return p.is_root
    if not in_subtree(node_id, p.scope_node_id, ancestors):
        return False
    return p.token_id in (node_owner, parent_owner)


def can_write_doc(p: Principal, node_id: int, node_owner: Optional[int], role: str,
                  ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(node_id, ancestors, kb_root):
        return p.is_root
    if not in_subtree(node_id, p.scope_node_id, ancestors):
        return False
    if role in OWNER_ONLY_ROLES:
        return p.token_id == node_owner
    if role in HOLDER_ROLES:
        return True
    return False


def can_edit_doc(p: Principal, node_id: int, role: str, author: int,
                 ancestors: Ancestors, kb_root: Optional[int]) -> bool:
    if is_kb(node_id, ancestors, kb_root):
        return p.is_root
    if author != p.token_id:
        return False
    if role in OWNER_ONLY_ROLES and node_id == p.scope_node_id and not p.is_root:
        return False
    return True


def can_answer_escalation(p: Principal, node_id: int, node_owner: Optional[int],
                          ancestors: Ancestors) -> bool:
    """The owner of the node (or its ancestors' owner chain holder) answers."""
    if not in_subtree(node_id, p.scope_node_id, ancestors):
        return False
    return p.token_id == node_owner or p.is_root


def can_mint(p: Principal, scope_node_id: int, child_can_spawn: bool, ancestors: Ancestors) -> bool:
    if not p.can_spawn:
        return False
    if child_can_spawn and not p.can_spawn:
        return False
    return in_subtree(scope_node_id, p.scope_node_id, ancestors)


def can_revoke(p: Principal, token_parent_id: Optional[int]) -> bool:
    return token_parent_id == p.token_id
