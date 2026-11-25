"""LocalClient facade: delegates each call to one child (task_runner, review_worker, quote_capture ports,
hook installer)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from planning_system.api_client import ClientSettings

from .interface import (ExchangeReaderPort, HookInstallerPort, LocalClientInterface, ReferenceId,
                        ReferenceSyncPort, ReviewModeFactory)
from .review_mode.serve_until_signalled import run_review_mode
from .review_worker import ReviewWorkerInterface
from .task_runner import RunningSession, TaskRunnerInterface, TaskStartRequest


class LocalClient(LocalClientInterface):

    def __init__(self, task_runner: TaskRunnerInterface, review_worker: ReviewWorkerInterface,
                 reference_sync: ReferenceSyncPort, exchange_reader: ExchangeReaderPort,
                 hook_installer: HookInstallerPort, review_mode_factory: Optional[ReviewModeFactory] = None):
        self._task_runner = task_runner
        self._review_worker = review_worker
        self._reference_sync = reference_sync
        self._exchange_reader = exchange_reader
        self._hook_installer = hook_installer
        self._review_mode_factory = review_mode_factory

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
        return self._review_worker.ask(question, [Path(p) for p in context_paths])

    def serve_reviews(self, project_id: int, backend: Optional[str] = None, model: Optional[str] = None,
                      poll_seconds: float = 5.0, once: bool = False) -> dict:
        if self._review_mode_factory is None:
            raise RuntimeError("this local client was built without review mode")
        return run_review_mode(self._review_mode_factory(project_id, backend, model, poll_seconds), once)


def build_local_client(settings: ClientSettings) -> LocalClientInterface:
    """Wires the real children (Claude Code adapter, file registry, quote_capture) for this install."""
    from planning_system.api_client import PlanningApiClient

    from .client_credentials import FileClientCredentials
    from .client_paths import ClientPaths
    from .harness_adapters import AdapterConfig, adapter_for
    from .harness_adapters.claude_code.install import ClaudeCodeHookInstaller
    from .quote_capture.jsonl_exchange_cache import JsonlExchangeCache
    from .quote_capture.production_ports import ApiServerReferences, StoredQuoteKey
    from .quote_capture.reference_sync import ReferenceSyncService
    from .quote_capture_bridge import CachedExchangeReader, ReferenceSyncAdapter
    from .review_mode import ReviewerBackendFactory, ReviewModeLoop
    from .review_worker import ReviewWorker
    from .task_runner import RunningSessionsRegistry, TaskRunner, TaskSessionLauncher

    paths = ClientPaths.from_environment()
    api = PlanningApiClient(settings)
    adapter = adapter_for(AdapterConfig(), session_logs_directory=paths.session_logs_directory)
    cache = JsonlExchangeCache(paths.exchange_cache_file)
    return LocalClient(
        task_runner=TaskRunner(TaskSessionLauncher(api, adapter, settings),
                               RunningSessionsRegistry(paths.running_sessions_file)),
        review_worker=ReviewWorker(adapter, thinking_log_path=paths.reviewer_thinking_log_file),
        reference_sync=ReferenceSyncAdapter(ReferenceSyncService(
            cache, ApiServerReferences(api), StoredQuoteKey(FileClientCredentials(paths.home)))),
        exchange_reader=CachedExchangeReader(cache),
        hook_installer=ClaudeCodeHookInstaller(),
        review_mode_factory=lambda project_id, backend, model, poll_seconds: ReviewModeLoop(
            api, ReviewerBackendFactory().create(backend, model), project_id, poll_seconds),
    )
