"""node_content: content on a node; text stored as fixed references (superseded-by chain on edit)."""


class NodeContentStore:
    def __init__(self, storage, references):
        self._storage = storage
        self._references = references

    def add(self, node_id, text, tags):
        raise NotImplementedError

    def replace(self, node_id, old_reference_id, new_text):
        raise NotImplementedError

    def list(self, node_id):
        raise NotImplementedError
