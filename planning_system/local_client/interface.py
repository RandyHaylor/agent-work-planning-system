"""Public interface of local_client (facade used by cli), plus the ports it needs from quote_capture and the
harness installer. quote_capture is built separately (05-spec-quote-capture.md); these ports are the slice
of its interface LocalClient calls, so this module does not import it."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from .task_runner import RunningSession, TaskStartRequest

ReferenceId = int


class ReferenceSyncPort(ABC):
    """quote_capture.ReferenceSync."""

    @abstractmethod
    def sync(self, local_exchange_id: str) -> ReferenceId: ...


class ExchangeReaderPort(ABC):
    """quote_capture's local cache reader (raw_input_log_reader)."""

    @abstractmethod
    def recent_exchanges(self, last: int) -> list[dict]: ...


class HookInstallerPort(ABC):
    """The harness's hook installer (Claude Code: harness_adapters/claude_code/install.py)."""

    @abstractmethod
    def install(self) -> None: ...


class LocalClientInterface(ABC):

    @abstractmethod
    def install_hooks(self) -> None: ...

    @abstractmethod
    def list_exchanges(self, last: int) -> list[dict]: ...

    @abstractmethod
    def cite_exchange(self, local_exchange_id: str) -> ReferenceId:
        """quote_capture.ReferenceSync: syncs exactly that exchange to the server."""

    @abstractmethod
    def start_task(self, request: TaskStartRequest) -> str:
        """Returns the session id; async, does not block."""

    @abstractmethod
    def stop_task(self, agent_id: str) -> None: ...

    @abstractmethod
    def running_tasks(self) -> list[RunningSession]: ...

    @abstractmethod
    def ask_reviewer(self, question: str, context_paths: Sequence[Path] = ()) -> str: ...
