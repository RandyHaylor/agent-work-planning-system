"""Types for context_assembly."""
from dataclasses import dataclass

NodeId = int


@dataclass(frozen=True)
class AssembledContext:
    node_id: NodeId
    text: str                        # the pre-prompt, ready to hand to an agent
    sources: tuple                   # tuple[NodeId, ...]: which nodes contributed, root first
