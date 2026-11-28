"""task_assigner: assign + mint in one call (ProjectTree.assign/update, CredentialIssuer.mint,
AgentRegistry.register as the "touch").

Order: check the node, mint, then write the node. Minting first means a refused or failed mint
leaves the node untouched even without a rollback; the caller's transaction covers the rest."""
from planning_system.contract import Invalid
from planning_system.server.domain.project_tree import ABANDONED, DONE

from .interface import TaskAssigner
from .ports import AgentRegistry, CredentialIssuer, ProjectTree
from .types import Assignment

WORKER = "worker"


class TaskAssignerService(TaskAssigner):
    def __init__(self, tree: ProjectTree, issuer: CredentialIssuer, agents: AgentRegistry):
        self._tree, self._issuer, self._agents = tree, issuer, agents

    def assign(self, issuer, node_id, agent_id, branch):
        node = self._assignable(node_id)
        credential = self._issuer.mint(issuer, WORKER, self._project_of(node), node.id, agent_id)
        self._agents.register(agent_id)
        self._tree.assign(node.id, agent_id)
        assigned = self._tree.update(node.id, branch=branch)
        return Assignment(assigned, credential.token, credential.credential_id)

    def _assignable(self, node_id):
        node = self._tree.get(node_id)
        if node.state in (DONE, ABANDONED):
            raise Invalid(f"node {node_id} is {node.state}")
        if self._tree.children(node_id):
            raise Invalid(f"node {node_id} has children; only a leaf task is assigned")
        return node

    def _project_of(self, node):
        ancestors = self._tree.ancestors(node.id)
        return ancestors[0].id if ancestors else node.id
