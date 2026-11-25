"""Per-project overrides for global settings + creation-time comment seeding."""
from __future__ import annotations

import json

import pytest

from source_of_truth import load_config
from source_of_truth.add_session_to_project_cli import add_session_to_project
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_reference_validator import (
    ReferenceValidationError,
    validate_raw_input_reference,
)


def _read_project_settings_json(project_id: str) -> dict:
    return json.loads(load_config.project_settings_file_path(project_id).read_text())


def test_fresh_project_seeds_override_comment_and_empty_overrides():
    add_session_to_project("proj-A", "sess-A", "/tmp/sessA.jsonl")
    raw = _read_project_settings_json("proj-A")
    assert load_config.PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY in raw
    # Comment lists every overridable global setting name.
    comment = raw[load_config.PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY]
    for name in load_config.OVERRIDABLE_GLOBAL_SETTING_NAMES:
        assert name in comment
    assert raw["overrides"] == {}


def test_generic_override_applies_for_any_global_setting():
    add_session_to_project("proj-B", "sess-B", "/tmp/sessB.jsonl")
    settings = load_config.load_project_settings("proj-B")
    settings.overrides = {"pre_submission_capture_char_limit": 4000}
    load_config.save_project_settings(settings)

    effective = load_config.resolve_effective_global_settings("proj-B")
    assert effective.pre_submission_capture_char_limit == 4000
    # Untouched settings still inherit the global default.
    assert effective.reviewer_mode == load_config.load_global_settings().reviewer_mode


def test_unknown_override_key_is_ignored():
    add_session_to_project("proj-C", "sess-C", "/tmp/sessC.jsonl")
    settings = load_config.load_project_settings("proj-C")
    settings.overrides = {"not_a_real_setting": 123}
    load_config.save_project_settings(settings)
    effective = load_config.resolve_effective_global_settings("proj-C")
    assert not hasattr(effective, "not_a_real_setting")
    assert effective.pre_submission_capture_char_limit == \
        load_config.load_global_settings().pre_submission_capture_char_limit


def test_dedicated_reviewer_mode_override_wins_over_generic_map():
    add_session_to_project("proj-D", "sess-D", "/tmp/sessD.jsonl")
    settings = load_config.load_project_settings("proj-D")
    settings.overrides = {"reviewer_mode": "deferred"}
    settings.reviewer_mode_override = "none"  # dedicated field should win
    load_config.save_project_settings(settings)
    assert load_config.resolve_reviewer_mode_for_project("proj-D") == "none"


def test_existing_project_add_session_does_not_inject_comment():
    add_session_to_project("proj-E", "sess-E1", "/tmp/e1.jsonl")
    # Simulate a project created before the comment feature: strip the comment.
    settings = load_config.load_project_settings("proj-E")
    settings.raw_extra.pop(load_config.PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY, None)
    load_config.save_project_settings(settings)

    add_session_to_project("proj-E", "sess-E2", "/tmp/e2.jsonl")  # existing file
    raw = _read_project_settings_json("proj-E")
    assert load_config.PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY not in raw


def test_validator_consumer_honors_project_char_range_threshold_override():
    pid = "proj-validator"
    add_session_to_project(pid, "s1", "/tmp/v.jsonl")
    # One raw-log entry whose submission is 100 chars long.
    append_submission_to_raw_input_log(pid, "s1", "x" * 100, "")
    reference_with_char_range = {"raw_input_id": 0, "char_range": [0, 10]}

    # Global default threshold is 500 -> a 100-char submission may NOT use char_range.
    with pytest.raises(ReferenceValidationError):
        validate_raw_input_reference(pid, reference_with_char_range)

    # Project override lowers the threshold to 50 -> 100 > 50, so char_range is allowed.
    settings = load_config.load_project_settings(pid)
    settings.overrides = {"char_range_allowed_above_threshold": 50}
    load_config.save_project_settings(settings)
    validate_raw_input_reference(pid, reference_with_char_range)  # must not raise


def test_writer_consumer_honors_project_capture_char_limit_override():
    pid = "proj-writer"
    add_session_to_project(pid, "s1", "/tmp/w.jsonl")
    settings = load_config.load_project_settings(pid)
    settings.overrides = {"pre_submission_capture_char_limit": 10}
    load_config.save_project_settings(settings)

    result = append_submission_to_raw_input_log(pid, "s1", "the user prompt", "y" * 100)
    # Pre-text truncated to the project's 10-char window, not the global 2000.
    assert result["pre_text_char_count"] == 10
