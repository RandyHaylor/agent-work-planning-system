"""postgres_halt_store: implements system_halt's HaltStoragePort. Declares halts (one row per halt in force;
scope "system" or "project:<id>")."""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Table, Text, delete, select
from sqlalchemy.engine import Connection

from planning_system.server.domain.system_halt import Halt, HaltStoragePort

from .metadata import METADATA

HALTS = Table(
    "halts", METADATA,
    Column("scope", Text, primary_key=True),
    Column("project_id", BigInteger),
    Column("halted_by", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("halted_at", DateTime(timezone=True), nullable=False),
)


def _scope(project_id) -> str:
    return "system" if project_id is None else f"project:{project_id}"


class PostgresHaltStore(HaltStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def all(self):
        return [Halt(r.project_id, r.halted_by, r.reason, r.halted_at)
                for r in self._conn.execute(select(HALTS).order_by(HALTS.c.scope))]

    def put(self, halt):
        self._conn.execute(delete(HALTS).where(HALTS.c.scope == _scope(halt.project_id)))
        self._conn.execute(HALTS.insert().values(scope=_scope(halt.project_id), project_id=halt.project_id,
                                                 halted_by=halt.halted_by, reason=halt.reason,
                                                 halted_at=halt.halted_at))

    def remove(self, project_id):
        return self._conn.execute(delete(HALTS).where(HALTS.c.scope == _scope(project_id))).rowcount > 0
