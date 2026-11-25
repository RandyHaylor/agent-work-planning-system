"""Ports agent_registry needs. Storage has no delete either."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .types import AgentId, AgentSession


class AgentRegistryStoragePort(ABC):
    @abstractmethod
    def get(self, agent_id: AgentId) -> Optional[AgentSession]: ...

    @abstractmethod
    def save(self, session: AgentSession) -> None:
        """Insert or replace by agent_id."""

    @abstractmethod
    def list(self) -> list[AgentSession]: ...


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
