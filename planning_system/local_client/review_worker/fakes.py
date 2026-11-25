"""Fake review worker: same reuse + rotate-once behaviour, no logging."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from ..harness_adapters import AiCliAdapterInterface, PersistentReviewerSessionHandle
from .interface import ReviewWorkerInterface
from .types import CONTEXT_EXHAUSTION_RESPONSE_MARKERS, REVIEWER_ALLOWED_TOOL_NAMES, REVIEWER_PRIMING_PROMPT


class FakeReviewWorker(ReviewWorkerInterface):

    def __init__(self, adapter: AiCliAdapterInterface, reviewer_model_name: str = "sonnet",
                 thinking_log_path: Optional[Path] = None,
                 allowed_tool_names: Sequence[str] = tuple(REVIEWER_ALLOWED_TOOL_NAMES)):
        self._adapter = adapter
        self._model = reviewer_model_name
        self._tools = list(allowed_tool_names)
        self._handle: Optional[PersistentReviewerSessionHandle] = None

    def ask(self, question: str, context_paths: Sequence[Path] = ()) -> str:
        prompt = question + "".join(f"\nContext file: {path}" for path in context_paths)
        answer = self._session().send_prompt_and_await_response(prompt)
        if any(marker in answer.lower() for marker in CONTEXT_EXHAUSTION_RESPONSE_MARKERS):
            self._handle.terminate()
            self._handle = None
            answer = self._session().send_prompt_and_await_response(prompt)
        return answer

    def _session(self) -> PersistentReviewerSessionHandle:
        if self._handle is None or not self._handle.is_alive():
            self._handle = self._adapter.spawn_persistent_reviewer_session(
                REVIEWER_PRIMING_PROMPT, [], self._tools, self._model)
        return self._handle
