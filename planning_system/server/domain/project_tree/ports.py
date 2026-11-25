"""Ports project_tree needs: tree_storage_port, a clock. ReferenceLibrary is a collaborator
(planning_system.server.domain.references.interface.ReferenceLibrary)."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from planning_system.server.domain.references.interface import ReferenceLibrary  # noqa: F401

from .types import Node, NodeContent, NodeId, ReferenceId


class TreeStoragePort(ABC):
    @abstractmethod
    def new_id(self) -> NodeId: ...

    @abstractmethod
    def get(self, node_id: NodeId) -> Optional[Node]: ...

    @abstractmethod
    def save(self, node: Node) -> None:
        """Insert or replace by id. There is no delete."""

    @abstractmethod
    def children(self, parent_id: Optional[NodeId]) -> list[Node]:
        """Any order."""

    @abstractmethod
    def subtree(self, root_id: NodeId) -> list[Node]:
        """The node and everything below it."""

    @abstractmethod
    def add_content(self, node_id: NodeId, content: NodeContent) -> None: ...

    @abstractmethod
    def replace_content(self, node_id: NodeId, old_reference_id: ReferenceId,
                        content: NodeContent) -> None: ...

    @abstractmethod
    def content(self, node_id: NodeId) -> list[NodeContent]: ...

    def all_nodes(self) -> list[Node]:
        """Every node (build log #40, for the citing-nodes lookup). Default walks each project's
        subtree; a store may override it with one query."""
        return [node for project in self.children(None) for node in self.subtree(project.id)]


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
