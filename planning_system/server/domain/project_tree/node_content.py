"""node_content: content on a node; text stored as fixed references (superseded-by chain on edit)."""
from planning_system.contract import NotFound

from .types import NodeContent


class NodeContentStore:
    def __init__(self, storage, references):
        self._storage = storage
        self._references = references

    def add(self, node_id, text, tags):
        self._require_node(node_id)
        reference = self._references.store_node_text(text, node_id)
        content = NodeContent(reference.id, frozenset(tags))
        self._storage.add_content(node_id, content)
        return content

    def replace(self, node_id, old_reference_id, new_text):
        old = next((c for c in self.list(node_id) if c.reference_id == old_reference_id), None)
        if old is None:
            raise NotFound(f"content {old_reference_id} on node {node_id}")
        reference = self._references.store_node_text(new_text, node_id, replaces=old_reference_id)
        content = NodeContent(reference.id, old.tags)
        self._storage.replace_content(node_id, old_reference_id, content)
        return content

    def list(self, node_id):
        self._require_node(node_id)
        return self._storage.content(node_id)

    def _require_node(self, node_id):
        if self._storage.get(node_id) is None:
            raise NotFound(f"node {node_id}")
