"""Public interface of agent_registry. There is deliberately no delete."""
from abc import ABC, abstractmethod

from .types import AgentId, AgentSession


class AgentRegistry(ABC):
    @abstractmethod
    def register(self, agent_id: AgentId, **metadata) -> AgentSession:
        """New entry, or update the given metadata + last_seen."""

    @abstractmethod
    def get(self, agent_id: AgentId) -> AgentSession: ...

    @abstractmethod
    def list(self) -> list[AgentSession]: ...
