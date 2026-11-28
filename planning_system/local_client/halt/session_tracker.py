"""ClientSessionTracker: records the processes this client starts in the running-sessions registry, so `planning
halt` can find them, and refuses new starts while the client is halted. It is the adapters' ProcessTracker (reviewer
`claude -p` turns) and the review loop's registration."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from ..harness_adapters import ProcessTracker
from ..task_runner import (SESSION_REVIEW_LOOP, SESSION_REVIEWER, RunningSession, RunningSessionsRegistryInterface)
from .halt_marker import HaltMarker


class ClientSessionTracker(ProcessTracker):

    def __init__(self, registry: RunningSessionsRegistryInterface, marker: HaltMarker):
        self._registry = registry
        self._marker = marker

    def ensure_not_halted(self) -> None:
        """Raises ClientHalted."""
        self._marker.ensure_not_halted()

    def is_halted(self) -> bool:
        return self._marker.is_set()

    # ProcessTracker (reviewer processes)
    def before_launch(self) -> None:
        self.ensure_not_halted()

    def launched(self, pid: int, label: str) -> None:
        self._registry.record(RunningSession(_key(SESSION_REVIEWER, pid), 0, label, os.getcwd(), pid,
                                             kind=SESSION_REVIEWER, process_group=True))

    def exited(self, pid: int) -> None:
        self._registry.forget(_key(SESSION_REVIEWER, pid))

    @contextmanager
    def review_loop(self, project_id: int) -> Iterator[None]:
        """Registers this process as a review loop for the duration (killed by pid alone: it runs in the caller's
        process group, which may hold the user's shell job)."""
        self.ensure_not_halted()
        pid = os.getpid()
        key = _key(SESSION_REVIEW_LOOP, pid)
        self._registry.record(RunningSession(key, project_id, "reviewer", os.getcwd(), pid,
                                             kind=SESSION_REVIEW_LOOP, process_group=False))
        try:
            yield
        finally:
            self._registry.forget(key)


def _key(kind: str, pid: int) -> str:
    return f"{kind}-{pid}"
