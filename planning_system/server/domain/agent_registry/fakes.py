"""Test support: in-memory storage, a settable clock and a fake registry."""
import dataclasses
from datetime import datetime, timedelta, timezone

from planning_system.contract import Invalid, NotFound

from .interface import AgentRegistry
from .ports import AgentRegistryStoragePort, Clock
from .types import METADATA_FIELDS, AgentSession


class FakeClock(Clock):
    def __init__(self, start: datetime | None = None):
        self.current = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self):
        return self.current

    def advance(self, delta: timedelta = timedelta(minutes=1)):
        self.current += delta


class InMemoryAgentRegistryStorage(AgentRegistryStoragePort):
    def __init__(self):
        self.rows: dict[str, AgentSession] = {}

    def get(self, agent_id):
        return self.rows.get(agent_id)

    def save(self, session):
        self.rows[session.agent_id] = session

    def list(self):
        return list(self.rows.values())


class FakeAgentRegistry(AgentRegistry):
    def __init__(self, storage, clock):
        self._storage, self._clock = storage, clock

    def register(self, agent_id, **metadata):
        unknown = set(metadata) - set(METADATA_FIELDS)
        if unknown:
            raise Invalid(f"unknown fields: {sorted(unknown)}")
        now = self._clock.now()
        given = {k: v for k, v in metadata.items() if v is not None}
        existing = self._storage.get(agent_id)
        if existing is None:
            session = AgentSession(agent_id=agent_id, first_seen=now, last_seen=now, **given)
        else:
            session = dataclasses.replace(existing, last_seen=now, **given)
        self._storage.save(session)
        return session

    def get(self, agent_id):
        session = self._storage.get(agent_id)
        if session is None:
            raise NotFound(agent_id)
        return session

    def list(self):
        return self._storage.list()
