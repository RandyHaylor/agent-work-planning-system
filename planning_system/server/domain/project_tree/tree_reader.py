"""Reads of the tree: get, children in order, ancestors root first, ready siblings, nodes by state."""
from planning_system.contract import NotFound

from .node import NodeReadiness


class TreeReader:
    def __init__(self, storage, readiness: NodeReadiness | None = None):
        self._storage = storage
        self._readiness = readiness or NodeReadiness()

    def get(self, node_id):
        node = self._storage.get(node_id)
        if node is None:
            raise NotFound(f"node {node_id}")
        return node

    def children(self, node_id):
        return sorted(self._storage.children(node_id), key=lambda n: n.position)

    def ancestors(self, node_id):
        chain, node = [], self.get(node_id)
        while node.parent_id is not None:
            node = self.get(node.parent_id)
            chain.append(node)
        chain.reverse()
        return chain

    def depth(self, node_id):
        """1 for a project (top-level) node."""
        return len(self.ancestors(node_id)) + 1

    def ready_siblings(self, parent_id):
        return self._readiness.ready(self.children(parent_id), lookup=self._storage.get)

    def list_nodes(self, project_id, state=None):
        self.get(project_id)
        nodes = sorted(self._storage.subtree(project_id), key=lambda n: n.id)
        return [n for n in nodes if state is None or n.state == state]
