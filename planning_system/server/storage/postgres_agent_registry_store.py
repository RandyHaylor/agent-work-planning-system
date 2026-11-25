"""postgres_agent_registry_store: implements agent_registry's AgentRegistryStoragePort. Declares
agent_sessions. No delete."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Table, Text
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from planning_system.server.domain.agent_registry.ports import AgentRegistryStoragePort
from planning_system.server.domain.agent_registry.types import METADATA_FIELDS, AgentSession

from .metadata import METADATA

AGENT_SESSIONS = Table(
    "agent_sessions", METADATA,
    Column("agent_id", Text, primary_key=True),
    Column("host", Text), Column("platform", Text), Column("model", Text),
    Column("path", Text), Column("system", Text), Column("url", Text),
    Column("first_seen", DateTime(timezone=True), nullable=False),
    Column("last_seen", DateTime(timezone=True), nullable=False),
)


class PostgresAgentRegistryStore(AgentRegistryStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def get(self, agent_id):
        found = self._sessions(select(AGENT_SESSIONS).where(AGENT_SESSIONS.c.agent_id == agent_id))
        return found[0] if found else None

    def save(self, session):
        """Upsert by agent_id."""
        row = {f: getattr(session, f) for f in ("agent_id", *METADATA_FIELDS, "first_seen", "last_seen")}
        statement = insert(AGENT_SESSIONS).values(**row)
        self._conn.execute(statement.on_conflict_do_update(
            index_elements=[AGENT_SESSIONS.c.agent_id],
            set_={k: statement.excluded[k] for k in row if k != "agent_id"}))

    def list(self):
        return self._sessions(select(AGENT_SESSIONS).order_by(AGENT_SESSIONS.c.first_seen,
                                                              AGENT_SESSIONS.c.agent_id))

    def _sessions(self, statement):
        return [AgentSession(**r._mapping) for r in self._conn.execute(statement)]
