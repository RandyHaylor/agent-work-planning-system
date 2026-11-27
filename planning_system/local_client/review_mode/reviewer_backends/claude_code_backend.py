"""claude_code: the existing ReviewWorker (persistent headless `claude -p` session via the Claude Code harness
adapter, rotation on context exhaustion). The factory builds the worker with no tools (quotes are inlined).
Every turn of a review goes to that session; each review opens with "NEW REVIEW ... ignore earlier reviews"
(build log #55)."""
from __future__ import annotations

from ...review_worker import ReviewWorkerInterface
from ..review_conversation import ReviewConversation
from .conversational_backend import ConversationalReviewerBackend
from .conversations import ReviewWorkerConversation

DEFAULT_CLAUDE_REVIEWER_MODEL = "haiku"


class ClaudeCodeBackend(ConversationalReviewerBackend):
    name = "claude_code"

    def __init__(self, review_worker: ReviewWorkerInterface):
        self._review_worker = review_worker

    def _open_conversation(self) -> ReviewConversation:
        return ReviewWorkerConversation(self._review_worker)
