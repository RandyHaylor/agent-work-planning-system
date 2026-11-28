"""transcript_pre_text: Claude Code's implementation of quote_capture's HarnessAdapterPort.

Pre-text = the agent's preceding turn, read from the session transcript at UserPromptSubmit time (carried from
SoT cli_entrypoint._extract_pre_text_from_transcript_for_prompt), so an interrupted turn still yields its
partial output. Best-effort: "" on any problem.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from planning_system.local_client.quote_capture.ports import HarnessAdapterPort

from . import transcript_events
from .claude_cli_get_recent_agent_messages import parse_events


class ClaudeCodeTranscriptPreText(HarnessAdapterPort):
    """Bound to one hook call: its session id, transcript path and the prompt being submitted."""

    def __init__(self, session_id: str, transcript_path: Optional[str], incoming_prompt_text: str):
        self._session_id = session_id
        self._transcript_path = Path(transcript_path) if transcript_path else None
        self._incoming_prompt_text = incoming_prompt_text

    def get_current_session_id(self) -> str:
        return self._session_id

    def get_preceding_agent_output(self, session_id: str) -> str:
        events = self._events()
        if not events:
            return ""
        try:
            return transcript_events.build_pre_text_for_incoming_user_prompt(events, self._incoming_prompt_text)
        except Exception:
            return ""

    def user_messages_sent_while_agent_was_working(self) -> list[str]:
        """Queued messages the user typed while the agent worked (they fire no hook of their own)."""
        events = self._events()
        if not events:
            return []
        try:
            return list(transcript_events.find_user_messages_sent_while_agent_was_working(events,
                                                                                  self._incoming_prompt_text))
        except Exception:
            return []

    def _events(self) -> list[dict]:
        if self._transcript_path is None or not self._transcript_path.exists():
            return []
        try:
            return list(parse_events(self._transcript_path))
        except Exception:
            return []
