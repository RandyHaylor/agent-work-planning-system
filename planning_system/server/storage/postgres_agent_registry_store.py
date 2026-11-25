"""postgres_agent_registry_store: implements agent_registry's AgentRegistryStoragePort. Declares
agent_sessions. No delete."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Table, Text
from sqlalchemy.engine import Connection

from planning_system.server.domain.agent_registry.ports import AgentRegistryStoragePort

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
        raise NotImplementedError("level 7")

    def save(self, session):
        raise NotImplementedError("level 7")   # upsert by agent_id

    def list(self):
        raise NotImplementedError("level 7")
