"""context_assembler: ancestors' context_summary + node's own content -> pre-prompt (hollow)."""
from .interface import ContextAssembler


class ContextAssemblerService(ContextAssembler):
    def __init__(self, tree, references):
        self._tree = tree
        self._references = references

    def assemble(self, node_id):
        raise NotImplementedError
