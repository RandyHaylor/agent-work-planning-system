"""claude_code: the existing ReviewWorker (persistent headless `claude -p` session via the Claude Code harness
adapter, rotation on context exhaustion). The factory builds the worker with no tools (quotes are inlined)."""
from __future__ import annotations

from ...review_worker import ReviewWorkerInterface
from ..types import ReviewerUnavailable
from .prompted_backend import PromptedReviewerBackend

DEFAULT_CLAUDE_REVIEWER_MODEL = "haiku"


class ClaudeCodeBackend(PromptedReviewerBackend):
    name = "claude_code"

    def __init__(self, review_worker: ReviewWorkerInterface):
        self._review_worker = review_worker

    def _ask(self, prompt: str) -> str:
        try:
            return self._review_worker.ask(prompt)
        except Exception as error:           # any harness failure (timeout, dead process) = backend unavailable
            raise ReviewerUnavailable(f"claude reviewer failed: {error}") from error
