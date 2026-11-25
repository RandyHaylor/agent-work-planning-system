"""Validates raw_input_id references in change-set operations against the raw log on disk.

Rules per spec:
  - raw_input_id must resolve to a real entry in the project's raw input log.
  - char_range is FORBIDDEN when submission length <= CHAR_RANGE_ALLOWED_ABOVE_THRESHOLD.
  - char_range is ALLOWED-BUT-OPTIONAL when submission length > threshold.
  - When char_range is present it must be in-bounds and at least MIN_CHAR_RANGE_LENGTH chars.
"""
from __future__ import annotations

from typing import Any

from .load_config import resolve_effective_global_settings
from .raw_input_log_reader import (
    RawLogEntryNotFoundError,
    get_raw_log_entry_by_raw_input_id,
)


class ReferenceValidationError(ValueError):
    pass


def validate_raw_input_reference(
    project_id: str, raw_input_reference: dict[str, Any]
) -> None:
    from .id_display import strip_raw_input_id_input_prefix

    # Accept an optional `raw-` display prefix on input; normalize to the bare id.
    raw_input_id = strip_raw_input_id_input_prefix(raw_input_reference.get("raw_input_id"))
    char_range = raw_input_reference.get("char_range")
    if raw_input_id is None or not isinstance(raw_input_id, int):
        raise ReferenceValidationError(
            f"raw_input_reference must include integer raw_input_id: {raw_input_reference}"
        )
    try:
        entry = get_raw_log_entry_by_raw_input_id(project_id, raw_input_id)
    except RawLogEntryNotFoundError as exc:
        raise ReferenceValidationError(str(exc)) from exc

    # Validate the optional agent pre-text selection (independent of char_range).
    # None/"all" or "none" need no bounds; a [start,end] line range must be in range.
    pre_text_line_range = raw_input_reference.get("pre_text_line_range")
    if isinstance(pre_text_line_range, (list, tuple)):
        if len(pre_text_line_range) != 2 or not all(isinstance(n, int) for n in pre_text_line_range):
            raise ReferenceValidationError(
                f"pre_text_line_range must be [start, end] integers; got {pre_text_line_range}"
            )
        start_line_number, end_line_number = pre_text_line_range
        pre_text_line_count = len(entry.pre_submission_content.split("\n")) if entry.pre_submission_content else 0
        if pre_text_line_count == 0:
            raise ReferenceValidationError(
                f"pre_text_line_range set but raw_input_id={raw_input_id} has no agent pre-text"
            )
        if start_line_number < 1 or end_line_number > pre_text_line_count or start_line_number > end_line_number:
            raise ReferenceValidationError(
                f"pre_text_line_range {list(pre_text_line_range)} out of bounds for "
                f"pre-text with {pre_text_line_count} lines"
            )
    elif pre_text_line_range not in (None, "none"):
        raise ReferenceValidationError(
            f"pre_text_line_range must be null, \"none\", or [start, end]; got {pre_text_line_range!r}"
        )

    submission_text_length = len(entry.submission_text)

    if char_range is None:
        return

    # Resolve the citation rules with this project's overrides applied
    # (project value if set, else global default).
    effective_settings = resolve_effective_global_settings(project_id)
    char_range_allowed_above_threshold = effective_settings.char_range_allowed_above_threshold
    min_char_range_length = effective_settings.min_char_range_length

    # char_range was provided -- it is only allowed when the submission is long enough
    # to need slicing.
    if submission_text_length <= char_range_allowed_above_threshold:
        raise ReferenceValidationError(
            f"char_range is only allowed when submission length > {char_range_allowed_above_threshold}; "
            f"this submission is {submission_text_length} chars, so cite the whole entry instead."
        )

    if not (isinstance(char_range, list) and len(char_range) == 2):
        raise ReferenceValidationError(f"char_range must be [start, end]; got {char_range}")
    start_char_index, end_char_index = char_range
    if not (isinstance(start_char_index, int) and isinstance(end_char_index, int)):
        raise ReferenceValidationError(f"char_range entries must be integers; got {char_range}")
    if start_char_index < 0 or end_char_index >= submission_text_length:
        raise ReferenceValidationError(
            f"char_range {char_range} out of bounds for entry of length {submission_text_length}"
        )
    if end_char_index < start_char_index:
        raise ReferenceValidationError(f"char_range end < start: {char_range}")
    range_length = (end_char_index - start_char_index) + 1
    if range_length < min_char_range_length:
        raise ReferenceValidationError(
            f"char_range length {range_length} below minimum {min_char_range_length}"
        )


def validate_change_set_references(
    project_id: str, change_set_operations: list[dict[str, Any]]
) -> None:
    for operation in change_set_operations:
        if "raw_input_reference" in operation and operation["raw_input_reference"] is not None:
            validate_raw_input_reference(project_id, operation["raw_input_reference"])
