"""Types for project_tree: one generic node type, and content attached to a node."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

NodeId = int
AgentId = str
ReferenceId = str

ASSIGNED, IN_PROGRESS, DONE, ABANDONED = "assigned", "in_progress", "done", "abandoned"
STATES = (ASSIGNED, IN_PROGRESS, DONE, ABANDONED)

TECH_SPIKE, REQUIREMENT_REQUEST = "tech spike", "requirement request"
SUPPLEMENTARY_LABELS = frozenset({TECH_SPIKE, REQUIREMENT_REQUEST})

LINEAR_LEVELS = 4   # levels 1-4 form a straight line; branching starts at level 5

# fields update() may change; state, assignee, parent and position have their own operations
EDITABLE_FIELDS = frozenset({"title", "level_label", "context_summary", "labels", "depends_on", "branch"})


@dataclass(frozen=True)
class Node:
    id: NodeId
    parent_id: Optional[NodeId]      # None = a project (top-level node)
    position: int                    # order among siblings
    title: str                       # generic topic, no claims
    level_label: str                 # "what we're doing", ..., "build"
    state: str                       # "assigned" | "in_progress" | "done" | "abandoned"
    labels: frozenset                # descriptive, e.g. "tech spike", "requirement request", "review"
    context_summary: str             # general "what this accomplishes"; passes down to every node below
    last_verified: datetime
    depends_on: Optional[tuple]      # tuple[NodeId, ...]; None = the previous sibling
    assignee: Optional[AgentId]      # key into agent_registry
    branch: Optional[str]            # which branch the task's work is on


@dataclass(frozen=True)
class ProjectCitation:
    """One citation inside one current content item of a node in a project."""
    node_id: NodeId
    content_reference_id: ReferenceId
    tags: frozenset
    citation: object                 # references.Citation (reference_id, start_line, end_line)


@dataclass(frozen=True)
class NodeContent:
    reference_id: ReferenceId        # text is a fixed reference (origin "node")
    tags: frozenset                  # descriptive
