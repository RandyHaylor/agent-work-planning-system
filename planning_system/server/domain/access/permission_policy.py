"""permission_policy: the real rules (hollow until level 7)."""
from .interface import PermissionPolicy


class RulePermissionPolicy(PermissionPolicy):
    def can_read_node(self, p, node, ancestors):
        raise NotImplementedError

    def can_read_reference(self, p, ref, nodes_citing_it):
        raise NotImplementedError

    def can_read_temp_entry(self, p, entry):
        raise NotImplementedError

    def can_read_knowledge_base(self, p, kb):
        raise NotImplementedError

    def can_create_node(self, p, parent):
        raise NotImplementedError

    def can_edit_node(self, p, node):
        raise NotImplementedError

    def can_set_state(self, p, node, new_state):
        raise NotImplementedError

    def can_assign(self, p, node):
        raise NotImplementedError

    def can_create_supplementary_task(self, p, task):
        raise NotImplementedError

    def can_answer_requirement_request(self, p, request):
        raise NotImplementedError

    def can_add_content(self, p, node):
        raise NotImplementedError

    def can_submit_user_quote(self, p):
        raise NotImplementedError

    def can_store_proposal_response(self, p):
        raise NotImplementedError

    def can_mint(self, p, scope, role):
        raise NotImplementedError

    def can_revoke(self, p, token_scope):
        raise NotImplementedError

    def can_rotate(self, p, token):
        raise NotImplementedError
