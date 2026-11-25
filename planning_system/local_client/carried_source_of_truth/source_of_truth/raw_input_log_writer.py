"""Append a raw input submission (and prior assistant pre-text) to the project's rolling raw log.

raw_input_id is assigned as the next integer in the project's log (counting all
existing entries across all sessions). timestamp_iso is recorded at second
resolution for human readability.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .load_config import (
    PRE_SUBMISSION_CAPTURE_CHAR_LIMIT,
    project_directory_for,
    project_raw_input_log_file_path,
    resolve_effective_global_settings,
)
from .cross_platform_file_lock import acquire_exclusive_file_lock
from .raw_input_log_entry_schema import RawInputLogEntry


def truncate_pre_text_to_capture_limit(
    prior_assistant_output_text: str,
    capture_char_limit: int = PRE_SUBMISSION_CAPTURE_CHAR_LIMIT,
) -> str:
    if len(prior_assistant_output_text) <= capture_char_limit:
        return prior_assistant_output_text
    return prior_assistant_output_text[-capture_char_limit:]


def _format_iso_seconds_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _count_existing_entries_in_log(log_data: dict) -> int:
    return sum(len(v) for v in log_data.values() if isinstance(v, list))


def append_submission_to_raw_input_log(
    project_id: str,
    session_id: str,
    submission_text: str,
    prior_assistant_output_text: str,
) -> dict[str, Any]:
    project_directory_for(project_id).mkdir(parents=True, exist_ok=True)
    log_file_path = project_raw_input_log_file_path(project_id)
    # Project override of the capture window if set, else the global default.
    capture_char_limit = resolve_effective_global_settings(
        project_id
    ).pre_submission_capture_char_limit

    with acquire_exclusive_file_lock(log_file_path):
        if log_file_path.exists():
            try:
                existing_log_data = json.loads(log_file_path.read_text())
            except json.JSONDecodeError:
                existing_log_data = {}
        else:
            existing_log_data = {}
        if not isinstance(existing_log_data, dict):
            existing_log_data = {}
        next_raw_input_id = _count_existing_entries_in_log(existing_log_data)
        entry = RawInputLogEntry(
            raw_input_id=next_raw_input_id,
            timestamp_iso=_format_iso_seconds_utc_now(),
            pre_submission_content=truncate_pre_text_to_capture_limit(
                prior_assistant_output_text, capture_char_limit
            ),
            submission_text=submission_text,
        )
        session_entries = existing_log_data.setdefault(session_id, [])
        session_entries.append(entry.to_json_dict())
        log_file_path.write_text(json.dumps(existing_log_data, indent=2))

    return {
        "raw_input_id": entry.raw_input_id,
        "timestamp_iso": entry.timestamp_iso,
        "session_id": session_id,
        "pre_text_char_count": len(entry.pre_submission_content),
        "additional_context_message": (
            f"[source-of-truth] Logged your submission at {entry.timestamp_iso} "
            f"as raw_input_id {entry.raw_input_id} for session_id {session_id}. "
            f"Pre-text captured: {len(entry.pre_submission_content)} chars. "
            f"Reference future change-set ops by raw_input_id."
        ),
    }
