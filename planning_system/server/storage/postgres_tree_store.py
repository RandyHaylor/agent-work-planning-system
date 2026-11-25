"""postgres_tree_store: implements project_tree's TreeStoragePort. Declares nodes, node_dependencies
and node_content. Never opens or commits a transaction; there is no delete."""
from __future__ import annotations

from sqlalchemy import (JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Table, Text)
from sqlalchemy.engine import Connection

from planning_system.server.domain.project_tree.ports import TreeStoragePort

from .metadata import METADATA

NODES = Table(
    "nodes", METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("parent_id", BigInteger, ForeignKey("nodes.id"), nullable=True, index=True),
    Column("position", Integer, nullable=False),
    Column("title", Text, nullable=False),
    Column("level_label", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("labels", JSON, nullable=False),
    Column("context_summary", Text, nullable=False),
    Column("last_verified", DateTime(timezone=True), nullable=False),
    # depends_on None means "the previous sibling"; an explicit list (even empty) is in node_dependencies
    Column("depends_on_explicit", Boolean, nullable=False, default=False),
    Column("assignee", Text, nullable=True),
    Column("branch", Text, nullable=True),
)

NODE_DEPENDENCIES = Table(
    "node_dependencies", METADATA,
    Column("node_id", BigInteger, ForeignKey("nodes.id"), primary_key=True),
    Column("depends_on_id", BigInteger, ForeignKey("nodes.id"), primary_key=True),
    Column("ordinal", Integer, nullable=False),
)

NODE_CONTENT = Table(
    "node_content", METADATA,
    Column("node_id", BigInteger, ForeignKey("nodes.id"), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("reference_id", Text, nullable=False),
    Column("tags", JSON, nullable=False),
)


class PostgresTreeStore(TreeStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def new_id(self):
        raise NotImplementedError("level 7")

    def get(self, node_id):
        raise NotImplementedError("level 7")

    def save(self, node):
        raise NotImplementedError("level 7")

    def children(self, parent_id):
        raise NotImplementedError("level 7")

    def subtree(self, root_id):
        raise NotImplementedError("level 7")   # recursive CTE

    def add_content(self, node_id, content):
        raise NotImplementedError("level 7")

    def replace_content(self, node_id, old_reference_id, content):
        raise NotImplementedError("level 7")

    def content(self, node_id):
        raise NotImplementedError("level 7")
