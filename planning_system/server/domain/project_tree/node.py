"""node: the node's state and dependency rules (the Node type itself is in types.py)."""
from .types import ABANDONED, DONE

FINISHED = (DONE, ABANDONED)   # abandoned dependencies are skipped, i.e. count as cleared


class NodeReadiness:
    def effective_depends_on(self, node, siblings):
        """depends_on, or the previous sibling when it is None."""
        if node.depends_on is not None:
            return tuple(node.depends_on)
        earlier = [s for s in sorted(siblings, key=lambda s: s.position) if s.position < node.position]
        return (earlier[-1].id,) if earlier else ()

    def ready(self, siblings, lookup=None):
        """Siblings not done/abandoned whose dependencies are all done (abandoned ones skipped).

        lookup(node_id) -> Node | None resolves a dependency outside the sibling set.
        """
        by_id = {s.id: s for s in siblings}

        def find(dep_id):
            return by_id.get(dep_id) or (lookup(dep_id) if lookup else None)

        return [node for node in siblings
                if node.state not in FINISHED
                and all(self._cleared(find(dep)) for dep in self.effective_depends_on(node, siblings))]

    @staticmethod
    def _cleared(dependency):
        return dependency is not None and dependency.state in FINISHED
