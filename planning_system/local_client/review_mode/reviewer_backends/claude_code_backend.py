"""claude_code: the existing ReviewWorker (persistent headless `claude -p` session via the Claude Code harness
adapter, rotation on context exhaustion)."""
from __future__ import annotations

from ...review_worker import ReviewWorkerInterface
from .prompted_backend import PromptedReviewerBackend

DEFAULT_CLAUDE_REVIEWER_MODEL = "haiku"


class ClaudeCodeBackend(PromptedReviewerBackend):
    name = "claude_code"

    def __init__(self, review_worker: ReviewWorkerInterface):
        self._review_worker = review_worker

    def _ask(self, prompt: str) -> str:
        raise NotImplementedError
