"""The real agent registry: a running list of agent sessions keyed by agent_id. Never deletes."""
from dataclasses import replace

from planning_system.errors import Invalid, NotFound

from .interface import AgentRegistry
from .types import METADATA_FIELDS, AgentSession


def _given_metadata(metadata: dict) -> dict:
    """The metadata fields actually given (None means 'not given'); rejects unknown fields."""
    unknown = set(metadata) - set(METADATA_FIELDS)
    if unknown:
        raise Invalid(f"unknown agent metadata fields: {sorted(unknown)}")
    return {name: value for name, value in metadata.items() if value is not None}


class AgentRegistryService(AgentRegistry):
    def __init__(self, storage, clock):
        self._storage = storage
        self._clock = clock

    def register(self, agent_id, **metadata):
        given = _given_metadata(metadata)
        now = self._clock.now()
        existing = self._storage.get(agent_id)
        if existing is None:
            session = AgentSession(agent_id=agent_id, first_seen=now, last_seen=now, **given)
        else:
            session = replace(existing, last_seen=now, **given)
        self._storage.save(session)
        return session

    def get(self, agent_id):
        session = self._storage.get(agent_id)
        if session is None:
            raise NotFound(f"agent {agent_id}")
        return session

    def list(self):
        return self._storage.list()
