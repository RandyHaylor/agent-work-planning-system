"""postgres_tree_store: implements project_tree's TreeStoragePort. Declares nodes, node_dependencies
and node_content. Never opens or commits a transaction; there is no delete."""
from __future__ import annotations

from sqlalchemy import (JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Table, Text)
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from planning_system.server.domain.project_tree import TreeStoragePort
from planning_system.server.domain.project_tree import Node, NodeContent

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
        return self._conn.execute(text("SELECT nextval(pg_get_serial_sequence('nodes', 'id'))")).scalar_one()

    def get(self, node_id):
        found = self._nodes(select(NODES).where(NODES.c.id == node_id))
        return found[0] if found else None

    def save(self, node):
        row = dict(id=node.id, parent_id=node.parent_id, position=node.position, title=node.title,
                   level_label=node.level_label, state=node.state, labels=sorted(node.labels),
                   context_summary=node.context_summary, last_verified=node.last_verified,
                   depends_on_explicit=node.depends_on is not None, assignee=node.assignee,
                   branch=node.branch)
        statement = insert(NODES).values(**row)
        self._conn.execute(statement.on_conflict_do_update(
            index_elements=[NODES.c.id], set_={k: statement.excluded[k] for k in row if k != "id"}))
        self._conn.execute(NODE_DEPENDENCIES.delete().where(NODE_DEPENDENCIES.c.node_id == node.id))
        if node.depends_on:
            self._conn.execute(NODE_DEPENDENCIES.insert(), [
                dict(node_id=node.id, depends_on_id=dep, ordinal=i) for i, dep in enumerate(node.depends_on)])

    def children(self, parent_id):
        condition = NODES.c.parent_id.is_(None) if parent_id is None else NODES.c.parent_id == parent_id
        return self._nodes(select(NODES).where(condition).order_by(NODES.c.position, NODES.c.id))

    def subtree(self, root_id):
        tree = select(NODES.c.id).where(NODES.c.id == root_id).cte("tree", recursive=True)
        tree = tree.union_all(select(NODES.c.id).where(NODES.c.parent_id == tree.c.id))
        return self._nodes(select(NODES).where(NODES.c.id.in_(select(tree.c.id))).order_by(NODES.c.id))

    def add_content(self, node_id, content):
        next_ordinal = select(func.coalesce(func.max(NODE_CONTENT.c.ordinal) + 1, 0)).where(
            NODE_CONTENT.c.node_id == node_id).scalar_subquery()
        self._conn.execute(NODE_CONTENT.insert().values(
            node_id=node_id, ordinal=next_ordinal, reference_id=content.reference_id,
            tags=sorted(content.tags)))

    def replace_content(self, node_id, old_reference_id, content):
        self._conn.execute(NODE_CONTENT.update().where(
            NODE_CONTENT.c.node_id == node_id, NODE_CONTENT.c.reference_id == old_reference_id).values(
            reference_id=content.reference_id, tags=sorted(content.tags)))

    def content(self, node_id):
        rows = self._conn.execute(select(NODE_CONTENT).where(NODE_CONTENT.c.node_id == node_id)
                                  .order_by(NODE_CONTENT.c.ordinal))
        return [NodeContent(r.reference_id, frozenset(r.tags)) for r in rows]

    def _nodes(self, statement) -> list[Node]:
        rows = self._conn.execute(statement).all()
        ids = [r.id for r in rows]
        deps: dict[int, list[int]] = {}
        if ids:
            for d in self._conn.execute(select(NODE_DEPENDENCIES).where(
                    NODE_DEPENDENCIES.c.node_id.in_(ids)).order_by(NODE_DEPENDENCIES.c.ordinal)):
                deps.setdefault(d.node_id, []).append(d.depends_on_id)
        return [Node(id=r.id, parent_id=r.parent_id, position=r.position, title=r.title,
                     level_label=r.level_label, state=r.state, labels=frozenset(r.labels),
                     context_summary=r.context_summary, last_verified=r.last_verified,
                     depends_on=tuple(deps.get(r.id, ())) if r.depends_on_explicit else None,
                     assignee=r.assignee, branch=r.branch) for r in rows]
