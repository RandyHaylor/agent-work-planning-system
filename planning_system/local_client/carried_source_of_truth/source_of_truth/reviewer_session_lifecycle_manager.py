"""Owns the long-lived reviewer subprocess for a project.

Detects context-exhaustion responses and rotates the reviewer, archiving the
exhausted session_id into project-settings.json's historical_reviewer_session_ids.
"""
from __future__ import annotations

from typing import Optional

from .ai_cli_adapter_interface import (
    AiCliAdapterInterface,
    PersistentReviewerSessionHandle,
)
from datetime import datetime, timezone

from .load_config import (
    load_project_settings,
    project_directory_for,
    project_raw_input_log_file_path,
    project_reviewer_thinking_log_file_path,
    project_source_of_truth_file_path,
    resolve_reviewer_model_name_for_project,
    save_project_settings,
)

CONTEXT_EXHAUSTION_RESPONSE_MARKERS: tuple[str, ...] = (
    "prompt is too long",
    "prompt too long",
    "context length exceeded",
    "context_length_exceeded",
    "maximum context",
)

REVIEWER_ALLOWED_TOOL_NAMES: list[str] = ["Read", "WebFetch", "WebSearch"]


def _build_priming_prompt_text(project_id: str) -> str:
    return (
        f"You are the source-of-truth reviewer. Be FAST. Be TERSE.\n"
        f"Project: {project_id}\n"
        f"Tree file: {project_source_of_truth_file_path(project_id)}\n"
        f"Raw log: {project_raw_input_log_file_path(project_id)}\n\n"
        f"How to think:\n"
        f"- internal reasoning = brief bullet-style FACT CHECKS only, never prose\n"
        f"- do NOT restate the prompt, do NOT pre-explain, do NOT hedge\n"
        f"- one fact-check per op, then commit to a verdict\n"
        f"- reason field <= 15 words, plain English, no waffle\n\n"
        f"Per-op fact-checks to run (mentally, not in output):\n"
        f"  * Does the cited slice match a definitive requirement statement?\n"
        f"  * Does pre_input_context support that interpretation?\n"
        f"  * Is this a clarification/ack/question rather than a requirement? -> reject\n"
        f"  * Duplicate of an existing tree node? -> reject\n\n"
        f"Output: EXACTLY ONE JSON object, nothing before or after, no markdown fence:\n"
        f'  {{"ops": [{{"index": 0, "approved": true, "reason": "<=15 words"}}, ...],\n'
        f'   "message": "<=20 words overall summary"}}'
    )


class ReviewerSessionLifecycleManager:
    def __init__(self, project_id: str, ai_cli_adapter: AiCliAdapterInterface) -> None:
        self._project_id = project_id
        self._ai_cli_adapter = ai_cli_adapter
        self._current_handle: Optional[PersistentReviewerSessionHandle] = None

    def get_or_spawn_current_reviewer(self) -> PersistentReviewerSessionHandle:
        if self._current_handle is not None and self._current_handle.is_alive():
            return self._current_handle

        def streaming_event_appender_for_this_reviewer(event_kind: str, event_body_text: str) -> None:
            # The handle's session_id is the same id we'll eventually log under;
            # for streaming events we don't have it yet at construction time so
            # we pass a placeholder and let the appender resolve dynamically.
            current_id = (
                self._current_handle.session_id
                if self._current_handle is not None else "spawning"
            )
            self._append_to_thinking_log(f"STREAM_{event_kind}", current_id, event_body_text)

        resolved_model_name = resolve_reviewer_model_name_for_project(self._project_id)
        self._append_to_thinking_log(
            "SPAWN", "(new)",
            f"resolved_reviewer_model_name={resolved_model_name}",
        )
        handle = self._ai_cli_adapter.spawn_persistent_reviewer_session(
            priming_prompt_text=_build_priming_prompt_text(self._project_id),
            allowed_read_paths=[
                str(project_directory_for(self._project_id)),
            ],
            allowed_tool_names=REVIEWER_ALLOWED_TOOL_NAMES,
            reviewer_model_name=resolved_model_name,
            streaming_event_appender=streaming_event_appender_for_this_reviewer,
        )
        self._current_handle = handle
        settings = load_project_settings(self._project_id)
        settings.current_reviewer_session_id = handle.session_id
        save_project_settings(settings)
        return handle

    def send_prompt_with_rotation_on_exhaustion(self, prompt_text: str) -> str:
        handle = self.get_or_spawn_current_reviewer()
        self._append_to_thinking_log("PROMPT", handle.session_id, prompt_text)
        response_text = handle.send_prompt_and_await_response(prompt_text)
        self._append_to_thinking_log("RESPONSE", handle.session_id, response_text)
        if self._response_indicates_context_exhaustion(response_text):
            self._append_to_thinking_log("ROTATE", handle.session_id, "context exhausted; rotating reviewer")
            self._archive_current_reviewer_and_rotate()
            handle = self.get_or_spawn_current_reviewer()
            self._append_to_thinking_log("PROMPT", handle.session_id, prompt_text)
            response_text = handle.send_prompt_and_await_response(prompt_text)
            self._append_to_thinking_log("RESPONSE", handle.session_id, response_text)
        return response_text

    def _append_to_thinking_log(self, kind: str, reviewer_session_id: str, body: str) -> None:
        log_file_path = project_reviewer_thinking_log_file_path(self._project_id)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        with log_file_path.open("a") as log_handle:
            log_handle.write(f"\n===== {timestamp_iso} | {kind} | reviewer={reviewer_session_id} =====\n")
            log_handle.write(body.rstrip() + "\n")

    def _response_indicates_context_exhaustion(self, response_text: str) -> bool:
        lowered = response_text.lower()
        return any(marker in lowered for marker in CONTEXT_EXHAUSTION_RESPONSE_MARKERS)

    def _archive_current_reviewer_and_rotate(self) -> None:
        if self._current_handle is None:
            return
        exhausted_session_id = self._current_handle.session_id
        try:
            self._current_handle.terminate()
        except Exception:
            pass
        self._current_handle = None
        settings = load_project_settings(self._project_id)
        if exhausted_session_id not in settings.historical_reviewer_session_ids:
            settings.historical_reviewer_session_ids.append(exhausted_session_id)
        settings.current_reviewer_session_id = None
        save_project_settings(settings)
