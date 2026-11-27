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
    labels: frozenset = frozenset()  # e.g. "review" (the review task, build log #49)
    state: Optional[str] = None


REVIEW_TASK_LABEL = "review"         # a worker on an in-progress task with this label may review its project
USER_QUOTE_ORIGINS = ("user_exchange", "proposal_response")   # the user's own words (references origins)


@dataclass(frozen=True)
class ReferenceFacts:
    reference_id: ReferenceId
    owner: Optional[AgentId] = None
    origin: Optional[str] = None     # e.g. "user_exchange"; planners may read the user's own words to cite them


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
