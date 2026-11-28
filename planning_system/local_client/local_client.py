"""LocalClient facade: delegates each call to one child (task_runner, review_worker, quote_capture ports,
hook installer, halt)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from planning_system.api_client import ClientSettings

from .halt import ClientSessionTracker, SessionHalter
from .interface import (ExchangeReaderPort, HookInstallerPort, LocalClientInterface, ReferenceId,
                        ReferenceSyncPort, ReviewModeFactory)
from .review_mode import ReviewerChoice
from .review_mode.review_log import ReviewLogFile
from .review_mode.serve_until_signalled import run_review_mode
from .review_worker import ReviewWorkerInterface
from .task_runner import RunningSession, TaskRunnerInterface, TaskStartRequest


class LocalClient(LocalClientInterface):

    def __init__(self, task_runner: TaskRunnerInterface, review_worker: ReviewWorkerInterface,
                 reference_sync: ReferenceSyncPort, exchange_reader: ExchangeReaderPort,
                 hook_installer: HookInstallerPort, review_mode_factory: Optional[ReviewModeFactory] = None,
                 session_tracker: Optional[ClientSessionTracker] = None,
                 session_halter: Optional[SessionHalter] = None, review_log: Optional[ReviewLogFile] = None):
        self._task_runner = task_runner
        self._review_worker = review_worker
        self._reference_sync = reference_sync
        self._exchange_reader = exchange_reader
        self._hook_installer = hook_installer
        self._review_mode_factory = review_mode_factory
        self._session_tracker = session_tracker
        self._session_halter = session_halter
        self._review_log = review_log

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
                      poll_seconds: float = 5.0, once: bool = False, profile: Optional[str] = None,
                      granularity: Optional[str] = None) -> dict:
        if self._review_mode_factory is None:
            raise RuntimeError("this local client was built without review mode")
        if self._session_tracker is not None:
            self._session_tracker.ensure_not_halted()
        choice = ReviewerChoice(profile, backend, model, granularity)
        return run_review_mode(self._review_mode_factory(project_id, choice, poll_seconds), once, project_id,
                               self._session_tracker)

    def halt(self) -> dict:
        return self._halter().halt()

    def resume(self) -> dict:
        return self._halter().resume()

    def review_log(self, review_id: Optional[str] = None, last: int = 20) -> list[dict]:
        if self._review_log is None:
            raise RuntimeError("this local client was built without a review log")
        return self._review_log.recent(review_id, last)

    def _halter(self) -> SessionHalter:
        if self._session_halter is None:
            raise RuntimeError("this local client was built without halt")
        return self._session_halter


def build_local_client(settings: ClientSettings) -> LocalClientInterface:
    """Wires the real children (Claude Code adapter, file registry, quote_capture) for this install."""
    from planning_system.api_client import PlanningApiClient

    from .client_credentials import FileClientCredentials
    from .client_paths import ClientPaths
    from .halt import client_session_control
    from .harness_adapters import AdapterConfig, adapter_for
    from .harness_adapters.claude_code.install import ClaudeCodeHookInstaller
    from .quote_capture.jsonl_exchange_cache import JsonlExchangeCache
    from .quote_capture.production_ports import ApiServerReferences, StoredQuoteKey
    from .quote_capture.reference_sync import ReferenceSyncService
    from .quote_capture_bridge import CachedExchangeReader, ReferenceSyncAdapter
    from .review_mode import ReviewerBackendFactory, ReviewModeLoop, load_reviewer_profiles
    from .review_mode.review_log import ReviewLogFile
    from .review_worker import ReviewWorker
    from .task_runner import RunningSessionsRegistry, TaskRunner, TaskSessionLauncher

    paths = ClientPaths.from_environment()
    api = PlanningApiClient(settings)
    tracker, halter = client_session_control(paths)
    adapter = adapter_for(AdapterConfig(), session_logs_directory=paths.session_logs_directory,
                          process_tracker=tracker)
    cache = JsonlExchangeCache(paths.exchange_cache_file)
    return LocalClient(
        task_runner=TaskRunner(TaskSessionLauncher(api, adapter, settings),
                               RunningSessionsRegistry(paths.running_sessions_file), tracker.ensure_not_halted),
        review_worker=ReviewWorker(adapter, thinking_log_path=paths.reviewer_thinking_log_file),
        reference_sync=ReferenceSyncAdapter(ReferenceSyncService(
            cache, ApiServerReferences(api), StoredQuoteKey(FileClientCredentials(paths.home)))),
        exchange_reader=CachedExchangeReader(cache),
        hook_installer=ClaudeCodeHookInstaller(),
        review_mode_factory=lambda project_id, choice, poll_seconds: ReviewModeLoop(
            api, ReviewerBackendFactory().create_from_profile(choice.resolve(load_reviewer_profiles()),
                                                              ReviewLogFile(paths.review_log_directory), project_id),
            project_id, poll_seconds, tracker.ensure_not_halted),
        review_log=ReviewLogFile(paths.review_log_directory),
        session_tracker=tracker,
        session_halter=halter,
    )
