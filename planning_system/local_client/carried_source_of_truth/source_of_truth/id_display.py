"""Centralized helpers for the node-id / raw-input-id display convention.

Two DISTINCT id concepts must never be conflated:
  - node ids (requirements-tree nodes): strings like "1","2" (quote leaves),
    "a","b" (groups), "0" the top-level parent sentinel. Displayed `nd-<id>`.
  - raw input ids (entries in the per-project raw_input_log): integers from 0.
    Displayed `raw-<id>`.

Canonical storage is ALWAYS bare ("2","e",22). Prefixes are display-only and
accepted-but-stripped on input, so on-disk bare ids round-trip unchanged.
"""
from __future__ import annotations

from typing import Any

NODE_ID_DISPLAY_PREFIX = "nd-"
RAW_INPUT_ID_DISPLAY_PREFIX = "raw-"


def format_node_id_for_display(node_id: Any) -> str:
    """Bare node id -> display form (e.g. "2" -> "nd-2")."""
    return f"{NODE_ID_DISPLAY_PREFIX}{node_id}"


def format_raw_input_id_for_display(raw_input_id: Any) -> str:
    """Bare raw-input id -> display form (e.g. 22 -> "raw-22")."""
    return f"{RAW_INPUT_ID_DISPLAY_PREFIX}{raw_input_id}"


def strip_node_id_input_prefix(value: Any) -> str:
    """Remove a single leading `nd-` if present; coerce to str. No-op for bare ids."""
    text = str(value)
    if text.startswith(NODE_ID_DISPLAY_PREFIX):
        return text[len(NODE_ID_DISPLAY_PREFIX):]
    return text


def strip_raw_input_id_input_prefix(value: Any) -> Any:
    """Remove a single leading `raw-` if present.

    Returns an int when the (stripped) value is an integer literal, else the
    original/stripped value unchanged. Non-string inputs (already ints) pass
    through untouched.
    """
    if not isinstance(value, str):
        return value
    text = value
    if text.startswith(RAW_INPUT_ID_DISPLAY_PREFIX):
        text = text[len(RAW_INPUT_ID_DISPLAY_PREFIX):]
    try:
        return int(text)
    except ValueError:
        return text
