"""Read-only access to entries in a project's raw_input_log.json by raw_input_id."""
from __future__ import annotations

import json
from typing import Optional

from .load_config import project_raw_input_log_file_path
from .raw_input_log_entry_schema import RawInputLogEntry


class RawLogEntryNotFoundError(LookupError):
    pass


class CharRangeOutOfBoundsError(ValueError):
    pass


def load_raw_log_for_project(project_id: str) -> dict[str, list[dict]]:
    log_file_path = project_raw_input_log_file_path(project_id)
    if not log_file_path.exists():
        return {}
    try:
        data = json.loads(log_file_path.read_text())
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def list_all_raw_log_entries_for_project(
    project_id: str,
) -> list[tuple[int, str, RawInputLogEntry]]:
    """Every raw-log entry across all member sessions, sorted by raw_input_id
    ascending. Returns (raw_input_id, session_id, entry) tuples."""
    log_data = load_raw_log_for_project(project_id)
    rows: list[tuple[int, str, RawInputLogEntry]] = []
    for session_id, session_entries in log_data.items():
        if not isinstance(session_entries, list):
            continue
        for raw_entry in session_entries:
            raw_input_id = int(raw_entry.get("raw_input_id", -1))
            rows.append((raw_input_id, session_id, RawInputLogEntry.from_json_dict(raw_entry)))
    rows.sort(key=lambda row: row[0])
    return rows


def get_raw_log_entry_by_raw_input_id(
    project_id: str, raw_input_id: int
) -> RawInputLogEntry:
    log_data = load_raw_log_for_project(project_id)
    for session_entries in log_data.values():
        for raw_entry in session_entries:
            if int(raw_entry.get("raw_input_id", -1)) == raw_input_id:
                return RawInputLogEntry.from_json_dict(raw_entry)
    raise RawLogEntryNotFoundError(
        f"raw_input_id={raw_input_id} not found in project={project_id}"
    )


def find_session_id_for_raw_input_id(
    project_id: str, raw_input_id: int
) -> str:
    log_data = load_raw_log_for_project(project_id)
    for session_id, session_entries in log_data.items():
        for raw_entry in session_entries:
            if int(raw_entry.get("raw_input_id", -1)) == raw_input_id:
                return session_id
    raise RawLogEntryNotFoundError(
        f"raw_input_id={raw_input_id} not found in project={project_id}"
    )


def split_pre_text_into_lines(pre_submission_content: str) -> list[str]:
    """1-indexed-friendly line list for an entry's agent pre-text (one block even
    when it spans multiple agent messages / tool results)."""
    if not pre_submission_content:
        return []
    return pre_submission_content.split("\n")


def select_pre_text(pre_submission_content: str, pre_text_line_range) -> str:
    """Apply a node's pre-text selection to an entry's pre_submission_content.

    pre_text_line_range:
      None        -> whole pre-text (default for every new node),
      "none"      -> exclude the pre-text,
      [start,end] -> only these 1-indexed inclusive lines.
    Returns "" when there is nothing to include.
    """
    if not pre_submission_content:
        return ""
    if pre_text_line_range == "none":
        return ""
    if isinstance(pre_text_line_range, (list, tuple)):
        start_line_number, end_line_number = pre_text_line_range
        lines = split_pre_text_into_lines(pre_submission_content)
        return "\n".join(lines[start_line_number - 1 : end_line_number])
    return pre_submission_content  # None / "all"


def resolve_quote_text_from_reference(
    project_id: str,
    raw_input_id: int,
    char_range: Optional[tuple[int, int]] = None,
    pre_text_line_range=None,
) -> str:
    """Resolve a citation's text: the user submission (optionally char-sliced),
    PREFIXED with the entry's agent pre-text per the node's pre_text_line_range
    selection. When the entry has no pre-text (or selection is "none"), only the
    submission is returned -- identical to the historical behavior."""
    entry = get_raw_log_entry_by_raw_input_id(project_id, raw_input_id)
    full_text = entry.submission_text
    if char_range is None:
        submission_part = full_text
    else:
        start_char_index, end_char_index = char_range
        if start_char_index < 0 or end_char_index >= len(full_text) or start_char_index > end_char_index:
            raise CharRangeOutOfBoundsError(
                f"char_range {char_range} out of bounds for entry of length {len(full_text)}"
            )
        submission_part = full_text[start_char_index : end_char_index + 1]

    pre_text_part = select_pre_text(entry.pre_submission_content, pre_text_line_range)
    if pre_text_part:
        return (
            "[agent pre-text]\n"
            f"{pre_text_part}\n"
            "[user submission]\n"
            f"{submission_part}"
        )
    return submission_part
