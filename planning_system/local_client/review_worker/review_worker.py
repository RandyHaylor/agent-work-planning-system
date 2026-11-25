"""ReviewWorker: adapted from SoT reviewer_session_lifecycle_manager.py (get_or_spawn /
send_with_rotation_on_exhaustion), minus SoT's project settings and requirements-tree priming (the planning
system has no local tree). The session is reused within this process.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from ..harness_adapters import AiCliAdapterInterface, PersistentReviewerSessionHandle
from .interface import ReviewWorkerInterface
from .types import CONTEXT_EXHAUSTION_RESPONSE_MARKERS, REVIEWER_ALLOWED_TOOL_NAMES, REVIEWER_PRIMING_PROMPT


class ReviewWorker(ReviewWorkerInterface):

    def __init__(self, adapter: AiCliAdapterInterface, reviewer_model_name: str = "sonnet",
                 thinking_log_path: Optional[Path] = None):
        self._adapter = adapter
        self._reviewer_model_name = reviewer_model_name
        self._thinking_log_path = thinking_log_path
        self._current_handle: Optional[PersistentReviewerSessionHandle] = None

    def ask(self, question: str, context_paths: Sequence[Path] = ()) -> str:
        prompt = question + "".join(f"\nContext file: {path}" for path in context_paths)
        handle = self._get_or_spawn_current_reviewer()
        answer = self._send(handle, prompt)
        if self._response_indicates_context_exhaustion(answer):
            self._log("ROTATE", handle.session_id, "context exhausted; rotating reviewer")
            self._rotate()
            answer = self._send(self._get_or_spawn_current_reviewer(), prompt)
        return answer

    def _get_or_spawn_current_reviewer(self) -> PersistentReviewerSessionHandle:
        if self._current_handle is not None and self._current_handle.is_alive():
            return self._current_handle

        def streaming_event_appender(event_kind: str, event_body_text: str) -> None:
            current_id = self._current_handle.session_id if self._current_handle is not None else "spawning"
            self._log(f"STREAM_{event_kind}", current_id, event_body_text)

        self._log("SPAWN", "(new)", f"reviewer_model_name={self._reviewer_model_name}")
        self._current_handle = self._adapter.spawn_persistent_reviewer_session(
            priming_prompt_text=REVIEWER_PRIMING_PROMPT,
            allowed_read_paths=[],
            allowed_tool_names=REVIEWER_ALLOWED_TOOL_NAMES,
            reviewer_model_name=self._reviewer_model_name,
            streaming_event_appender=streaming_event_appender,
        )
        return self._current_handle

    def _send(self, handle: PersistentReviewerSessionHandle, prompt: str) -> str:
        self._log("PROMPT", handle.session_id, prompt)
        answer = handle.send_prompt_and_await_response(prompt)
        self._log("RESPONSE", handle.session_id, answer)
        return answer

    def _rotate(self) -> None:
        if self._current_handle is None:
            return
        try:
            self._current_handle.terminate()
        except Exception:
            pass
        self._current_handle = None

    @staticmethod
    def _response_indicates_context_exhaustion(response_text: str) -> bool:
        lowered = response_text.lower()
        return any(marker in lowered for marker in CONTEXT_EXHAUSTION_RESPONSE_MARKERS)

    def _log(self, kind: str, reviewer_session_id: str, body: str) -> None:
        if self._thinking_log_path is None:
            return
        self._thinking_log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._thinking_log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n===== {timestamp} | {kind} | reviewer={reviewer_session_id} =====\n")
            log.write(body.rstrip() + "\n")
