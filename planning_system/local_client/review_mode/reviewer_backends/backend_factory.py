"""ReviewerBackendFactory: backend name (from client config / `--backend`) -> backend. Adding a harness = one class
plus one entry in _builders. pi is parked (user 2026-11-26) and not selectable here."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from planning_system.errors import Invalid
from planning_system.model_calls import ModelEndpointFactory, load_model_endpoints

from ...review_worker import ReviewWorkerInterface
from ..bulk_review import BulkReview
from ..kind_dispatch import ReviewByKind
from ..node_guess_screen import NodeGuessScreen
from ..review_method import BULK, ReviewMethod
from ..reviewer_profiles import ReviewerProfile
from ..sentence_review import SentenceBySentenceReview
from .claude_code_backend import DEFAULT_CLAUDE_REVIEWER_MODEL, ClaudeCodeBackend
from .interface import ReviewerBackend
from .one_shot_backend import OneShotReviewerBackend

DEFAULT_BACKEND = "local_llm"
BACKEND_NAMES = ("local_llm", "claude_code")
DEFAULT_LOCAL_ENDPOINT = "local_gemma4"
# This repo's endpoints file (model_calls itself knows no repo layout); $PLANNING_MODEL_ENDPOINTS_FILE overrides it.
DEFAULT_MODEL_ENDPOINTS_FILE = Path(__file__).resolve().parents[4] / "config" / "model_endpoints.json"

ReviewWorkerFactory = Callable[[str], ReviewWorkerInterface]   # model name -> review worker


def review_method_for(granularity: str) -> ReviewMethod:
    """Content reviews at the granularity; whole-node reviews always by the one-call guess screen."""
    content = BulkReview() if granularity == BULK else SentenceBySentenceReview()
    return ReviewByKind(content, NodeGuessScreen())


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
    """model_endpoints defaults to this repo's endpoints file (read on first local_llm use); `model` for local_llm
    overrides the endpoint's configured model."""

    def __init__(self, review_worker_factory: Optional[ReviewWorkerFactory] = None,
                 model_endpoints: Optional[ModelEndpointFactory] = None,
                 local_endpoint_name: str = DEFAULT_LOCAL_ENDPOINT):
        self._review_worker_factory = review_worker_factory or claude_code_review_worker
        self._model_endpoints = model_endpoints
        self._local_endpoint_name = local_endpoint_name
        self._builders: dict[str, Callable[[Optional[str]], ReviewerBackend]] = {
            "local_llm": lambda model: OneShotReviewerBackend(
                self._endpoints().create(self._local_endpoint_name, model)),
            "claude_code": lambda model: ClaudeCodeBackend(
                self._review_worker_factory(model or DEFAULT_CLAUDE_REVIEWER_MODEL)),
        }

    def create(self, name: Optional[str] = None, model: Optional[str] = None,
               granularity: Optional[str] = None) -> ReviewerBackend:
        """granularity: per_sentence | bulk; default per_sentence for local_llm, bulk otherwise."""
        backend_name = name or DEFAULT_BACKEND
        builder = self._builders.get(backend_name)
        if builder is None:
            raise Invalid(f"unknown reviewer backend {name!r}; choose one of {', '.join(BACKEND_NAMES)}")
        profile = ReviewerProfile("(flags)", backend_name, model, granularity)
        return builder(model).use_review_method(review_method_for(profile.resolved_granularity()))

    def create_from_profile(self, profile: ReviewerProfile) -> ReviewerBackend:
        return self.create(profile.backend, profile.model, profile.granularity)

    def _endpoints(self) -> ModelEndpointFactory:
        if self._model_endpoints is None:
            self._model_endpoints = load_model_endpoints(default_path=DEFAULT_MODEL_ENDPOINTS_FILE)
        return self._model_endpoints
