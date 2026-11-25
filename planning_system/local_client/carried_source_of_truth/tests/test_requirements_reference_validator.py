from __future__ import annotations

import pytest

from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_reference_validator import (
    ReferenceValidationError,
    validate_raw_input_reference,
)


def test_rejects_unknown_raw_input_id():
    with pytest.raises(ReferenceValidationError):
        validate_raw_input_reference("p", {"raw_input_id": 9999})


def test_accepts_short_submission_without_char_range():
    log_result = append_submission_to_raw_input_log("p", "s", "yes", "")
    validate_raw_input_reference("p", {"raw_input_id": log_result["raw_input_id"]})


def test_short_submission_does_NOT_require_char_range():
    """Per spec: submissions <= threshold are referenced as a whole (no char_range needed)."""
    long_text = "x" * 800  # > 500
    short_text = "x" * 100  # <= 500
    long_result = append_submission_to_raw_input_log("p", "s", long_text, "")
    short_result = append_submission_to_raw_input_log("p", "s", short_text, "")
    # Both should validate without char_range.
    validate_raw_input_reference("p", {"raw_input_id": long_result["raw_input_id"]})
    validate_raw_input_reference("p", {"raw_input_id": short_result["raw_input_id"]})


def test_char_range_FORBIDDEN_when_submission_at_or_under_threshold():
    short_result = append_submission_to_raw_input_log("p", "s", "x" * 100, "")
    with pytest.raises(ReferenceValidationError) as exc:
        validate_raw_input_reference("p", {
            "raw_input_id": short_result["raw_input_id"],
            "char_range": [0, 0],
        })
    assert "only allowed when submission length >" in str(exc.value)


def test_char_range_allowed_above_threshold_with_valid_bounds():
    long_result = append_submission_to_raw_input_log("p", "s", "x" * 800, "")
    validate_raw_input_reference("p", {
        "raw_input_id": long_result["raw_input_id"],
        "char_range": [0, 99],
    })


def test_rejects_out_of_bounds_char_range_above_threshold():
    long_result = append_submission_to_raw_input_log("p", "s", "x" * 800, "")
    with pytest.raises(ReferenceValidationError):
        validate_raw_input_reference("p", {
            "raw_input_id": long_result["raw_input_id"],
            "char_range": [0, 5000],
        })


def test_rejects_char_range_with_end_less_than_start():
    long_result = append_submission_to_raw_input_log("p", "s", "x" * 800, "")
    with pytest.raises(ReferenceValidationError):
        validate_raw_input_reference("p", {
            "raw_input_id": long_result["raw_input_id"],
            "char_range": [50, 10],
        })
