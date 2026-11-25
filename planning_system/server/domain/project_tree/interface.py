"""ProjectTree: the one public interface of project_tree. No delete exists."""
from abc import ABC, abstractmethod
from typing import Iterable, Optional

from .types import AgentId, Node, NodeContent, NodeId, ReferenceId


class ProjectTree(ABC):
    # reading
    @abstractmethod
    def get(self, node_id: NodeId) -> Node: ...

    @abstractmethod
    def children(self, node_id: NodeId) -> list[Node]:
        """In position order."""

    @abstractmethod
    def ancestors(self, node_id: NodeId) -> list[Node]:
        """Root first."""

    @abstractmethod
    def content(self, node_id: NodeId) -> list[NodeContent]: ...

    @abstractmethod
    def ready_siblings(self, parent_id: NodeId) -> list[Node]:
        """Not done/abandoned, and everything in depends_on is done (abandoned ones skipped)."""

    @abstractmethod
    def citing_nodes(self, reference_id: ReferenceId) -> list[Node]:
        """Nodes whose content is that reference or whose content text cites it (build log #40)."""

    @abstractmethod
    def list_nodes(self, project_id: NodeId, state: Optional[str] = None) -> list[Node]:
        """Nodes in a project (the project node included), optionally by state (decision #17)."""

    # writing (each updates the summary or at least last_verified)
    @abstractmethod
    def create(self, parent_id: Optional[NodeId], title: str, level_label: str, context_summary: str,
               labels: Iterable[str] = (), depends_on: Optional[tuple] = None,
               position: Optional[int] = None) -> Node: ...

    @abstractmethod
    def insert_before(self, task_id: NodeId, title: str, labels: Iterable[str],
                      context_summary: str) -> Node:
        """Requirement request or tech spike: new sibling before the task, always added to its depends_on."""

    @abstractmethod
    def update(self, node_id: NodeId, **fields) -> Node: ...

    @abstractmethod
    def move(self, node_id: NodeId, new_parent_id: Optional[NodeId], position: int) -> Node: ...

    @abstractmethod
    def set_state(self, node_id: NodeId, state: str) -> Node: ...

    @abstractmethod
    def assign(self, node_id: NodeId, assignee: AgentId) -> Node:
        """Sets state to "assigned"."""

    @abstractmethod
    def add_content(self, node_id: NodeId, text: str, tags: Iterable[str]) -> NodeContent:
        """Stores text via ReferenceLibrary."""

    @abstractmethod
    def replace_content(self, node_id: NodeId, old_reference_id: ReferenceId,
                        new_text: str) -> NodeContent:
        """New reference that supersedes the old one."""
