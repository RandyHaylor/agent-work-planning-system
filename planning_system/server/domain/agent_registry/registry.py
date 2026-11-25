"""The real agent registry (hollow until level 7)."""
from .interface import AgentRegistry


class AgentRegistryService(AgentRegistry):
    def __init__(self, storage, clock):
        self._storage = storage
        self._clock = clock

    def register(self, agent_id, **metadata):
        raise NotImplementedError

    def get(self, agent_id):
        raise NotImplementedError

    def list(self):
        raise NotImplementedError
