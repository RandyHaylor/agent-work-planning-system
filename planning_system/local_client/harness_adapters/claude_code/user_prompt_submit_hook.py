"""UserPromptSubmit hook for Claude Code: writes the verbatim prompt + pre-text (preceding agent output,
via claude_cli_get_recent_agent_messages) to quote_capture's local cache. Nothing is sent to the server.

Ported from SoT cli_entrypoint._handle_user_prompt_submit_hook: same payload keys, same look-behind back-fill of
messages queued while the agent was working (captured first, empty pre-text, so ids stay chronological).
SoT's per-project session gating is dropped: every prompt is captured locally (05-spec-quote-capture.md).
Any failure prints {} so the user's session is never blocked.
"""
from __future__ import annotations

import json
import sys
from typing import Callable, Optional

from planning_system.local_client.client_paths import ClientPaths
from planning_system.local_client.quote_capture.exchange_capture import ExchangeCaptureService
from planning_system.local_client.quote_capture.jsonl_exchange_cache import JsonlExchangeCache
from planning_system.local_client.quote_capture.ports import HarnessAdapterPort, LocalExchangeCachePort
from planning_system.local_client.quote_capture.production_ports import SystemClock

from .transcript_pre_text import ClaudeCodeTranscriptPreText


class _NoPreText(HarnessAdapterPort):
    """Back-filled queued messages have no preceding agent turn of their own (SoT: empty pre-text)."""

    def __init__(self, session_id: str):
        self._session_id = session_id

    def get_current_session_id(self) -> str:
        return self._session_id

    def get_preceding_agent_output(self, session_id: str) -> str:
        return ""


def _default_cache() -> LocalExchangeCachePort:
    return JsonlExchangeCache(ClientPaths.from_environment().exchange_cache_file)


def handle_user_prompt_submit(hook_payload: dict,
                              cache_factory: Callable[[], LocalExchangeCachePort] = _default_cache) -> dict:
    """Claude Code hook stdin JSON -> hook stdout JSON."""
    session_id = hook_payload.get("session_id") or hook_payload.get("sessionId") or "unknown-session"
    submission_text = (hook_payload.get("prompt") or hook_payload.get("user_prompt")
                       or hook_payload.get("userPrompt") or "")
    transcript_path = hook_payload.get("transcript_path") or hook_payload.get("transcriptPath")

    transcript = ClaudeCodeTranscriptPreText(session_id, transcript_path, submission_text)
    cache = cache_factory()
    backfill = ExchangeCaptureService(_NoPreText(session_id), cache, SystemClock())
    for missed_message in transcript.user_messages_sent_while_agent_was_working():
        backfill.capture_prompt(session_id, missed_message)
    local_id = ExchangeCaptureService(transcript, cache, SystemClock()).capture_prompt(session_id, submission_text)
    return {"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (f"planning: this prompt is saved locally as exchange {local_id}; to quote it, "
                              f"run `planning cite-exchange {local_id}` and cite the returned reference."),
    }}


def main(stdin=None, stdout=None, cache_factory: Optional[Callable[[], LocalExchangeCachePort]] = None) -> int:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    try:
        payload = json.loads(stdin.read() or "{}")
        output = handle_user_prompt_submit(payload, cache_factory or _default_cache)
    except Exception:
        output = {}
    print(json.dumps(output), file=stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
