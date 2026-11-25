"""Test support: a working TaskAssigner over the collaborators' fakes."""
from planning_system.contract import Invalid
from planning_system.server.domain.project_tree.types import ABANDONED, DONE

from .interface import TaskAssigner
from .types import Assignment


class FakeTaskAssigner(TaskAssigner):
    def __init__(self, tree, issuer, agents):
        self._tree, self._issuer, self._agents = tree, issuer, agents

    def assign(self, issuer, node_id, agent_id, branch):
        node = self._tree.get(node_id)
        if node.state in (DONE, ABANDONED):
            raise Invalid(f"node {node_id} is {node.state}")
        if self._tree.children(node_id):
            raise Invalid(f"node {node_id} is not a leaf task")
        project_id = self._tree.ancestors(node_id)[0].id if node.parent_id is not None else node.id
        credential = self._issuer.mint(issuer, "worker", project_id, node_id, agent_id)  # mint first
        self._agents.register(agent_id)
        self._tree.assign(node_id, agent_id)
        assigned = self._tree.update(node_id, branch=branch)
        return Assignment(assigned, credential.token, credential.credential_id)
