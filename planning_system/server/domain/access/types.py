"""Types for access. Callers pass in the tree facts the rules need (access does no I/O)."""
from dataclasses import dataclass
from typing import Optional

from planning_system.contract import ROLES, Principal

NodeId = int
AgentId = str
ReferenceId = str
CredentialId = str

ADMIN, PLANNER, WORKER, QUOTE_CLIENT = ROLES

__all__ = [
    "Principal", "NodeFacts", "ReferenceFacts", "TempEntryFacts", "KnowledgeBaseFacts",
    "CredentialScope", "ADMIN", "PLANNER", "WORKER", "QUOTE_CLIENT",
]


@dataclass(frozen=True)
class NodeFacts:
    """What the rules need to know about a node."""
    node_id: NodeId
    project_id: NodeId               # the top-level (parentless) node it sits under; itself for a project
    assignee: Optional[AgentId] = None


@dataclass(frozen=True)
class ReferenceFacts:
    reference_id: ReferenceId
    owner: Optional[AgentId] = None


@dataclass(frozen=True)
class TempEntryFacts:
    cache_id: str
    owner: AgentId                   # the agent that fetched it


@dataclass(frozen=True)
class KnowledgeBaseFacts:
    kb_id: NodeId
    assigned_agent_ids: frozenset = frozenset()


@dataclass(frozen=True)
class CredentialScope:
    """The scope of a credential being minted, rotated or revoked."""
    role: str
    project_id: Optional[NodeId] = None
    scope_node_id: Optional[NodeId] = None
