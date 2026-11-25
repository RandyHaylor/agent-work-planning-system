"""node: the node's state and dependency rules (the Node type itself is in types.py)."""


class NodeReadiness:
    def effective_depends_on(self, node, siblings):
        """depends_on, or the previous sibling when it is None."""
        raise NotImplementedError

    def ready(self, siblings):
        """Siblings not done/abandoned whose dependencies are all done (abandoned ones skipped)."""
        raise NotImplementedError
