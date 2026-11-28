"""context_assembler: ancestors' context_summary + node's own content -> pre-prompt.

Reads the tree on every call (nothing cached), so a changed summary shows up next time.
"""
from planning_system.server.domain.project_tree import ABANDONED

from .interface import ContextAssembler
from .types import AssembledContext

SECTION_SEPARATOR = "\n\n"


class ContextAssemblerService(ContextAssembler):
    def __init__(self, tree, references):
        self._tree = tree
        self._references = references

    def assemble(self, node_id):
        node = self._tree.get(node_id)
        story = self._live_ancestors(node_id)
        parts = [ancestor.context_summary for ancestor in story] + self._own_content_texts(node_id)
        sources = tuple(ancestor.id for ancestor in story) + (node.id,)
        return AssembledContext(node.id, SECTION_SEPARATOR.join(parts), sources)

    def _live_ancestors(self, node_id):
        """Ancestors root first, abandoned ones left out ("abandoned means gone")."""
        return [a for a in self._tree.ancestors(node_id) if a.state != ABANDONED]

    def _own_content_texts(self, node_id):
        return [self._references.get(c.reference_id).text for c in self._tree.content(node_id)]
