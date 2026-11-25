"""Append-and-drain queue of user-facing messages produced by SoT API calls.

The submit_requirements_tree_change_set API (and any other SoT operation that
wants to surface text to the human user, not the AI agent) appends a line here.
A PostToolUse hook then drains the queue and emits each message via the
`systemMessage` field of its hook JSON output, which Claude Code shows to
the user but NOT to the agent.

File format: JSON Lines (one message per line). Drain rewrites the file empty.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .load_config import SOURCE_OF_TRUTH_ROOT_DIR
from .cross_platform_file_lock import acquire_exclusive_file_lock


def _pending_messages_file_path() -> Path:
    return SOURCE_OF_TRUTH_ROOT_DIR / "pending_user_messages.jsonl"


def add_pending_message_for_raw_input_sender(
    message_text: str,
    target_project_id: str,
    source_label: str = "source-of-truth",
) -> None:
    """Queue a user-facing message tagged with the project_id it's destined for.

    The PostToolUse emitter only drains messages whose target_project_id
    matches the currently-firing session's project, so other concurrent
    SoT projects never see each other's messages.
    """
    file_path = _pending_messages_file_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    line_payload = json.dumps({
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "target_project_id": target_project_id,
        "source_label": source_label,
        "message_text": message_text,
    })
    with acquire_exclusive_file_lock(file_path):
        with file_path.open("a") as file_handle:
            file_handle.write(line_payload + "\n")


def show_pending_messages_to_raw_input_sender_for_project(target_project_id: str) -> list[dict]:
    """Remove and return messages targeting the given project; leave others in queue."""
    file_path = _pending_messages_file_path()
    if not file_path.exists():
        return []
    drained_messages: list[dict] = []
    retained_lines: list[str] = []
    with acquire_exclusive_file_lock(file_path):
        try:
            raw_text = file_path.read_text()
        except OSError:
            return []
        for line in raw_text.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            try:
                parsed = json.loads(line_stripped)
            except json.JSONDecodeError:
                continue
            if parsed.get("target_project_id") == target_project_id:
                drained_messages.append(parsed)
            else:
                retained_lines.append(line_stripped)
        file_path.write_text(("\n".join(retained_lines) + "\n") if retained_lines else "")
    return drained_messages
