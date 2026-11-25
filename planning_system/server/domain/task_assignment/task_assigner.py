"""task_assigner: assign + mint in one call (ProjectTree.assign/update, CredentialIssuer.mint,
AgentRegistry.register as the "touch")."""
from .interface import TaskAssigner
from .ports import AgentRegistry, CredentialIssuer, ProjectTree


class TaskAssignerService(TaskAssigner):
    def __init__(self, tree: ProjectTree, issuer: CredentialIssuer, agents: AgentRegistry):
        self._tree, self._issuer, self._agents = tree, issuer, agents

    def assign(self, issuer, node_id, agent_id, branch):
        raise NotImplementedError("level 7")
