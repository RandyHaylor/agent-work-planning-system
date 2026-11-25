"""Fakes for local_client: a working facade, quote_capture port fakes, and a recording client for cli tests."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from planning_system.api_client import PlanningApiClientInterface

from .client_credentials import ClientCredentialsInterface
from .interface import (ExchangeReaderPort, HookInstallerPort, LocalClientInterface, ReferenceId,
                        ReferenceSyncPort)
from .review_worker import ReviewWorkerInterface
from .task_runner import RunningSession, TaskRunnerInterface, TaskStartRequest


class FakeExchangeCache(ExchangeReaderPort):
    """Stands in for quote_capture's local cache."""

    def __init__(self, exchanges: Optional[dict[str, dict]] = None):
        self.exchanges = dict(exchanges or {})

    def recent_exchanges(self, last: int) -> list[dict]:
        return [{"local_id": key, **value} for key, value in list(self.exchanges.items())[-last:]]


class FakeReferenceSync(ReferenceSyncPort):
    """Reads one exchange from the cache and stores it with the quote key (the only reader of the key)."""

    def __init__(self, api: PlanningApiClientInterface, cache: FakeExchangeCache,
                 credentials: ClientCredentialsInterface):
        self._api = api
        self._cache = cache
        self._credentials = credentials

    def sync(self, local_exchange_id: str) -> ReferenceId:
        exchange = self._cache.exchanges[local_exchange_id]
        quote_client = self._api.with_token(self._credentials.read_quote_key())
        return quote_client.store_user_exchange(exchange["session_id"], exchange["user_message"],
                                                exchange["pre_text"])["reference_id"]


class FakeHookInstaller(HookInstallerPort):

    def __init__(self):
        self.installs = 0

    def install(self) -> None:
        self.installs += 1


class FakeLocalClient(LocalClientInterface):

    def __init__(self, task_runner: TaskRunnerInterface, review_worker: ReviewWorkerInterface,
                 reference_sync: ReferenceSyncPort, exchange_reader: ExchangeReaderPort,
                 hook_installer: HookInstallerPort):
        self._task_runner = task_runner
        self._review_worker = review_worker
        self._reference_sync = reference_sync
        self._exchange_reader = exchange_reader
        self._hook_installer = hook_installer

    def install_hooks(self) -> None:
        self._hook_installer.install()

    def list_exchanges(self, last: int) -> list[dict]:
        return self._exchange_reader.recent_exchanges(last)

    def cite_exchange(self, local_exchange_id: str) -> ReferenceId:
        return self._reference_sync.sync(local_exchange_id)

    def start_task(self, request: TaskStartRequest) -> str:
        return self._task_runner.start_task(request)

    def stop_task(self, agent_id: str) -> None:
        self._task_runner.stop_task(agent_id)

    def running_tasks(self) -> list[RunningSession]:
        return self._task_runner.running_tasks()

    def ask_reviewer(self, question: str, context_paths: Sequence[Path] = ()) -> str:
        return self._review_worker.ask(question, context_paths)


class RecordingLocalClient(LocalClientInterface):
    """Records (method, arguments); for cli tests."""

    def __init__(self):
        self.calls: list = []

    def _record(self, name: str, **arguments):
        self.calls.append((name, arguments))
        return {"called": name}

    def install_hooks(self):
        return self._record("install_hooks")

    def list_exchanges(self, last):
        return self._record("list_exchanges", last=last)

    def cite_exchange(self, local_exchange_id):
        return self._record("cite_exchange", local_exchange_id=local_exchange_id)

    def start_task(self, request):
        return self._record("start_task", request=request)

    def stop_task(self, agent_id):
        return self._record("stop_task", agent_id=agent_id)

    def running_tasks(self):
        return self._record("running_tasks")

    def ask_reviewer(self, question, context_paths=()):
        return self._record("ask_reviewer", question=question, context_paths=tuple(context_paths))
