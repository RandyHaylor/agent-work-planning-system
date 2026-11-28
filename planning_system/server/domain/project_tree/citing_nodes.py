"""citing_nodes: which nodes cite a reference. A node cites reference X when X is one of its content
items, or when one of its content texts carries a citation `[X:start-end]` (build log #40; the
reference read rule is "anyone who can read a citing node")."""
from planning_system.server.domain.references import cites


class CitingNodesFinder:
    def __init__(self, storage, references):
        self._storage = storage
        self._references = references

    def find(self, reference_id):
        return [node for node in self._storage.all_nodes() if self._cites(node.id, reference_id)]

    def _cites(self, node_id, reference_id):
        for content in self._storage.content(node_id):
            if content.reference_id == reference_id:
                return True
            if cites(self._references.get(content.reference_id, follow_superseded=False).text, reference_id):
                return True
        return False
