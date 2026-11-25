"""Public interface of context_assembly."""
from abc import ABC, abstractmethod

from .types import AssembledContext, NodeId


class ContextAssembler(ABC):
    @abstractmethod
    def assemble(self, node_id: NodeId) -> AssembledContext:
        """Every non-abandoned ancestor's context_summary, root first, then all of the node's own
        content. Reads the tree only (ProjectTree.ancestors / get / content); nothing cached."""
