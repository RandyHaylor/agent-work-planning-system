"""context_assembly: pre-prompt for a node (spec: planning/05-spec-context-assembly.md).

Public surface: import from this package, not its files. `fakes` stays a separate
test-support submodule."""
from .context_assembler import ContextAssemblerService
from .interface import ContextAssembler
from .types import AssembledContext, NodeId

__all__ = ["AssembledContext", "ContextAssembler", "ContextAssemblerService", "NodeId"]
