"""Test support: a fake ContextAssembler."""
from planning_system.server.domain.project_tree import ABANDONED

from .interface import ContextAssembler
from .types import AssembledContext


class FakeContextAssembler(ContextAssembler):
    def __init__(self, tree, references):
        self._tree, self._refs = tree, references

    def assemble(self, node_id):
        node = self._tree.get(node_id)
        ancestors = [a for a in self._tree.ancestors(node_id) if a.state != ABANDONED]
        parts = [a.context_summary for a in ancestors]
        parts += [self._refs.get(c.reference_id).text for c in self._tree.content(node_id)]
        sources = tuple(a.id for a in ancestors) + (node.id,)
        return AssembledContext(node_id, "\n\n".join(parts), sources)
