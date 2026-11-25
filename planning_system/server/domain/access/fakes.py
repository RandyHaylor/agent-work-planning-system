"""Test support: a simple table-driven policy that follows the spec's rules."""
from .interface import PermissionPolicy
from .types import ADMIN, PLANNER, QUOTE_CLIENT, WORKER


def _in_project(p, project_id):
    return p.role == PLANNER and p.project_id is not None and p.project_id == project_id


def _own_task(p, node):
    return p.role == WORKER and p.scope_node_id is not None and p.scope_node_id == node.node_id


class TablePermissionPolicy(PermissionPolicy):
    def can_read_node(self, p, node, ancestors):
        return p.role == ADMIN or _in_project(p, node.project_id) or _own_task(p, node)

    def can_read_reference(self, p, ref, nodes_citing_it):
        return p.role == ADMIN or any(self.can_read_node(p, n, ()) for n in nodes_citing_it)

    def can_read_temp_entry(self, p, entry):
        return p.role == ADMIN or (p.agent_id is not None and p.agent_id == entry.owner)

    def can_read_knowledge_base(self, p, kb):
        if p.role in (ADMIN, PLANNER):
            return True
        return p.role == WORKER and p.agent_id in kb.assigned_agent_ids

    def can_create_node(self, p, parent):
        return p.role == ADMIN or _in_project(p, parent.project_id)

    def can_edit_node(self, p, node):
        return p.role == ADMIN or _in_project(p, node.project_id)

    def can_set_state(self, p, node, new_state):
        return p.role == ADMIN or _in_project(p, node.project_id)

    def can_assign(self, p, node):
        return p.role == ADMIN or _in_project(p, node.project_id)

    def can_create_supplementary_task(self, p, task):
        return p.role == ADMIN or _in_project(p, task.project_id) or _own_task(p, task)

    def can_answer_requirement_request(self, p, request):
        return p.role == ADMIN or (p.agent_id is not None and p.agent_id == request.assignee)

    def can_add_content(self, p, node):
        return p.role == ADMIN or _in_project(p, node.project_id) or _own_task(p, node)

    def can_submit_user_quote(self, p):
        return p.role == QUOTE_CLIENT

    def can_store_proposal_response(self, p):
        return p.role == ADMIN

    def can_mint(self, p, scope, role):
        if p.role == ADMIN:
            return role in (PLANNER, WORKER, QUOTE_CLIENT)
        # decision #20: a planner may also mint a planner (dev manager) inside its own project
        return role in (WORKER, PLANNER) and _in_project(p, scope.project_id)

    def can_revoke(self, p, token_scope):
        return p.role == ADMIN or _in_project(p, token_scope.project_id)

    def can_rotate(self, p, token):
        return p.role == ADMIN or _in_project(p, token.project_id)
