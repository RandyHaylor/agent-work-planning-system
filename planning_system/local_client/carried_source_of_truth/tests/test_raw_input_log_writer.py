from __future__ import annotations

import json

from source_of_truth.load_config import (
    PRE_SUBMISSION_CAPTURE_CHAR_LIMIT,
    project_raw_input_log_file_path,
)
from source_of_truth.raw_input_log_writer import (
    append_submission_to_raw_input_log,
    truncate_pre_text_to_capture_limit,
)


def test_truncate_pre_text_keeps_only_tail_chars():
    long_pretext = "abcdefg" * 1000  # 7000 chars
    truncated = truncate_pre_text_to_capture_limit(long_pretext)
    assert len(truncated) == PRE_SUBMISSION_CAPTURE_CHAR_LIMIT
    assert long_pretext.endswith(truncated)


def test_append_groups_entries_under_session_id_key():
    append_submission_to_raw_input_log("proj-x", "session-a", "first", "")
    append_submission_to_raw_input_log("proj-x", "session-a", "second", "")
    append_submission_to_raw_input_log("proj-x", "session-b", "third", "")

    log_data = json.loads(project_raw_input_log_file_path("proj-x").read_text())
    assert set(log_data.keys()) == {"session-a", "session-b"}
    assert len(log_data["session-a"]) == 2
    assert len(log_data["session-b"]) == 1
    # session_id is NOT duplicated as a property on each entry
    assert "session_id" not in log_data["session-a"][0]


def test_raw_input_id_is_assigned_sequentially_starting_at_zero_across_sessions():
    r0 = append_submission_to_raw_input_log("proj-x", "session-a", "first", "")
    r1 = append_submission_to_raw_input_log("proj-x", "session-a", "second", "")
    r2 = append_submission_to_raw_input_log("proj-x", "session-b", "third", "")
    assert r0["raw_input_id"] == 0
    assert r1["raw_input_id"] == 1
    assert r2["raw_input_id"] == 2


def test_timestamp_iso_is_at_second_resolution_no_microseconds():
    result = append_submission_to_raw_input_log("proj-x", "session-a", "hi", "")
    assert "." not in result["timestamp_iso"]  # no fractional seconds
    assert result["timestamp_iso"].endswith("+00:00")


def test_append_returns_additional_context_message_with_raw_input_id_and_timestamp():
    result = append_submission_to_raw_input_log("proj-x", "session-a", "hi", "prior text")
    assert str(result["raw_input_id"]) in result["additional_context_message"]
    assert result["timestamp_iso"] in result["additional_context_message"]
    assert "session-a" in result["additional_context_message"]
