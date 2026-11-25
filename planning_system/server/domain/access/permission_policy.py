"""permission_policy: the real rules (spec: planning/05-spec-access.md).

Carried from the old server's permissions.py approach: pure predicates over the principal and
the tree facts the caller passes in. A worker reads its ancestors' context summaries through
context_assembly, not by reading the ancestor nodes, so can_read_node grants a worker its own
task only.
"""
from .interface import PermissionPolicy
from .types import ADMIN, PLANNER, QUOTE_CLIENT, WORKER

MINTABLE_BY_ADMIN = frozenset({PLANNER, WORKER, QUOTE_CLIENT})
MINTABLE_BY_PLANNER = frozenset({PLANNER, WORKER})   # decision #20: a planner may mint a dev manager


def _is_admin(p):
    return p.role == ADMIN


def _plans_project(p, project_id):
    return p.role == PLANNER and p.project_id is not None and p.project_id == project_id


def _works_on(p, node):
    return p.role == WORKER and p.scope_node_id is not None and p.scope_node_id == node.node_id


def _manages(p, node):
    """Admin, or a planner inside the node's project."""
    return _is_admin(p) or _plans_project(p, node.project_id)


class RulePermissionPolicy(PermissionPolicy):
    # reading
    def can_read_node(self, p, node, ancestors):
        return _manages(p, node) or _works_on(p, node)

    def can_read_reference(self, p, ref, nodes_citing_it):
        return _is_admin(p) or any(self.can_read_node(p, n, ()) for n in nodes_citing_it)

    def can_read_temp_entry(self, p, entry):
        return _is_admin(p) or (p.agent_id is not None and p.agent_id == entry.owner)

    def can_read_knowledge_base(self, p, kb):
        if p.role in (ADMIN, PLANNER):
            return True
        return p.role == WORKER and p.agent_id in kb.assigned_agent_ids

    # tree writes
    def can_create_node(self, p, parent):
        return _manages(p, parent)

    def can_edit_node(self, p, node):
        return _manages(p, node)

    def can_set_state(self, p, node, new_state):
        return _manages(p, node)

    def can_assign(self, p, node):
        return _manages(p, node)

    def can_create_supplementary_task(self, p, task):
        return _manages(p, task) or _works_on(p, task)

    def can_answer_requirement_request(self, p, request):
        return _is_admin(p) or (p.agent_id is not None and p.agent_id == request.assignee)

    def can_add_content(self, p, node):
        return _manages(p, node) or _works_on(p, node)

    # references
    def can_submit_user_quote(self, p):
        return p.role == QUOTE_CLIENT

    def can_store_proposal_response(self, p):
        return _is_admin(p)

    # credentials
    def can_mint(self, p, scope, role):
        if _is_admin(p):
            return role in MINTABLE_BY_ADMIN
        return role in MINTABLE_BY_PLANNER and _plans_project(p, scope.project_id)

    def can_revoke(self, p, token_scope):
        return _is_admin(p) or _plans_project(p, token_scope.project_id)

    def can_rotate(self, p, token):
        return _is_admin(p) or _plans_project(p, token.project_id)
