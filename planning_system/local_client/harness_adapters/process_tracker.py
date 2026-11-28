"""ProcessTracker: the port an adapter calls around every model process it launches, so the client can find and
kill them (`planning halt`, build log #68). The adapter knows nothing about registries or halt markers."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProcessTracker(ABC):

    @abstractmethod
    def before_launch(self) -> None:
        """Raises to refuse the launch (e.g. the client is halted)."""

    @abstractmethod
    def launched(self, pid: int, label: str) -> None:
        """The process runs as the leader of its own process group (pid = process group id)."""

    @abstractmethod
    def exited(self, pid: int) -> None: ...


class NoProcessTracking(ProcessTracker):

    def before_launch(self) -> None:
        pass

    def launched(self, pid: int, label: str) -> None:
        pass

    def exited(self, pid: int) -> None:
        pass
