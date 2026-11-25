"""Reads of the tree: get, children in order, ancestors root first, ready siblings, nodes by state."""
from .node import NodeReadiness


class TreeReader:
    def __init__(self, storage, readiness: NodeReadiness | None = None):
        self._storage = storage
        self._readiness = readiness or NodeReadiness()

    def get(self, node_id):
        raise NotImplementedError

    def children(self, node_id):
        raise NotImplementedError

    def ancestors(self, node_id):
        raise NotImplementedError

    def ready_siblings(self, parent_id):
        raise NotImplementedError

    def list_nodes(self, project_id, state=None):
        raise NotImplementedError
