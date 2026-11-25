"""ReviewerBackendFactory: backend name (from client config / `--backend`) -> backend. Adding a harness = one class
plus one entry in _builders."""
from __future__ import annotations

from typing import Callable, Optional

import httpx

from planning_system.contract import Invalid

from ...review_worker import ReviewWorkerInterface
from .claude_code_backend import DEFAULT_CLAUDE_REVIEWER_MODEL, ClaudeCodeBackend
from .interface import ReviewerBackend
from .local_llm_backend import DEFAULT_LOCAL_LLM_MODEL, LocalLlmBackend
from .pi_backend import DEFAULT_PI_MODEL, PiBackend

DEFAULT_BACKEND = "local_llm"
BACKEND_NAMES = ("local_llm", "claude_code", "pi")

ReviewWorkerFactory = Callable[[str], ReviewWorkerInterface]   # model name -> review worker


def claude_code_review_worker(model: str) -> ReviewWorkerInterface:
    """The production worker: Claude Code adapter, no tools (quotes are inlined), thinking log in the client home."""
    from ...client_paths import ClientPaths
    from ...harness_adapters import AdapterConfig, adapter_for
    from ...review_worker import ReviewWorker

    paths = ClientPaths.from_environment()
    adapter = adapter_for(AdapterConfig(), session_logs_directory=paths.session_logs_directory)
    return ReviewWorker(adapter, reviewer_model_name=model, thinking_log_path=paths.reviewer_thinking_log_file,
                        allowed_tool_names=[])


class ReviewerBackendFactory:

    def __init__(self, review_worker_factory: Optional[ReviewWorkerFactory] = None,
                 http_transport: Optional[httpx.BaseTransport] = None):
        self._review_worker_factory = review_worker_factory or claude_code_review_worker
        self._http_transport = http_transport
        self._builders: dict[str, Callable[[Optional[str]], ReviewerBackend]] = {
            "local_llm": lambda model: LocalLlmBackend(model=model or DEFAULT_LOCAL_LLM_MODEL,
                                                       transport=self._http_transport),
            "claude_code": lambda model: ClaudeCodeBackend(
                self._review_worker_factory(model or DEFAULT_CLAUDE_REVIEWER_MODEL)),
            "pi": lambda model: PiBackend(model=model or DEFAULT_PI_MODEL),
        }

    def create(self, name: Optional[str] = None, model: Optional[str] = None) -> ReviewerBackend:
        builder = self._builders.get(name or DEFAULT_BACKEND)
        if builder is None:
            raise Invalid(f"unknown reviewer backend {name!r}; choose one of {', '.join(BACKEND_NAMES)}")
        return builder(model)
