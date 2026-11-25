"""Ports quote_capture needs.

HarnessAdapterPort is the slice of SoT's AiCliAdapterInterface (local_client/harness_adapters) that
capture uses; any adapter implementing it (Claude Code now, Codex later) plugs in unchanged.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .types import Exchange, LocalExchangeId, ReferenceId


class LocalExchangeCachePort(ABC):
    @abstractmethod
    def append(self, exchange: Exchange) -> None: ...

    @abstractmethod
    def get(self, local_id: LocalExchangeId) -> Optional[Exchange]: ...


class ServerReferencesPort(ABC):
    """POST /references/user-exchange through api_client."""

    @abstractmethod
    def store_user_exchange(self, credential: str, session_id: str, user_message: str,
                            pre_text: str) -> ReferenceId: ...


class HarnessAdapterPort(ABC):
    @abstractmethod
    def get_current_session_id(self) -> str: ...

    @abstractmethod
    def get_preceding_agent_output(self, session_id: str) -> str:
        """The agent output of the turn before the prompt (partial if that turn was interrupted)."""


class ClientCredentialsPort(ABC):
    """client_credentials: the install's quote key."""

    @abstractmethod
    def quote_key(self) -> str: ...


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
