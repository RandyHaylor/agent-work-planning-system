"""LocalClient facade: delegates each call to one child (task_runner, review_worker, quote_capture ports,
hook installer). Level 6 scaffold: hollow."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from planning_system.api_client import ClientSettings

from .interface import (ExchangeReaderPort, HookInstallerPort, LocalClientInterface, ReferenceId,
                        ReferenceSyncPort)
from .review_worker import ReviewWorkerInterface
from .task_runner import RunningSession, TaskRunnerInterface, TaskStartRequest


class LocalClient(LocalClientInterface):

    def __init__(self, task_runner: TaskRunnerInterface, review_worker: ReviewWorkerInterface,
                 reference_sync: ReferenceSyncPort, exchange_reader: ExchangeReaderPort,
                 hook_installer: HookInstallerPort):
        self._task_runner = task_runner
        self._review_worker = review_worker
        self._reference_sync = reference_sync
        self._exchange_reader = exchange_reader
        self._hook_installer = hook_installer

    def install_hooks(self) -> None:
        raise NotImplementedError("level 7")

    def list_exchanges(self, last: int) -> list[dict]:
        raise NotImplementedError("level 7")

    def cite_exchange(self, local_exchange_id: str) -> ReferenceId:
        raise NotImplementedError("level 7")

    def start_task(self, request: TaskStartRequest) -> str:
        raise NotImplementedError("level 7")

    def stop_task(self, agent_id: str) -> None:
        raise NotImplementedError("level 7")

    def running_tasks(self) -> list[RunningSession]:
        raise NotImplementedError("level 7")

    def ask_reviewer(self, question: str, context_paths: Sequence[Path] = ()) -> str:
        raise NotImplementedError("level 7")


def build_local_client(settings: ClientSettings) -> LocalClientInterface:
    """Wires the real children (Claude Code adapter, file registry, quote_capture) for this install."""
    raise NotImplementedError("level 7")
