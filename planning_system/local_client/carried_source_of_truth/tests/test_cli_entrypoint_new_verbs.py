"""Unit tests for the new CLI verbs: init-and-register and set-mode."""
from __future__ import annotations

import sys

import pytest

from source_of_truth import load_config as config_module
from source_of_truth.cli_entrypoint import (
    _handle_init_and_register,
    _handle_set_mode,
)
from source_of_truth.load_config import (
    REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    load_project_settings,
)
from source_of_truth.requirements_tree_store import load_requirements_tree


def test_init_and_register_creates_project_and_adds_session(capsys):
    return_code = _handle_init_and_register(
        ["sess-alpha", "/some/conversation/path.jsonl"]
    )
    assert return_code == 0
    settings = load_project_settings("sess-alpha")
    member_session_ids = [
        member.get("session_id") for member in settings.member_sessions
    ]
    assert "sess-alpha" in member_session_ids
    # Empty tree should exist on disk for that project_id.
    tree = load_requirements_tree("sess-alpha")
    assert tree.project_id == "sess-alpha"


def test_init_and_register_is_idempotent_for_already_present_session(capsys):
    _handle_init_and_register(["sess-beta", "/x"])
    _handle_init_and_register(["sess-beta", "/x"])  # second call
    captured = capsys.readouterr()
    assert "already_present" in captured.out


def test_init_and_register_rejects_wrong_argv_count():
    return_code = _handle_init_and_register(["only-one-arg"])
    assert return_code == 2


def test_set_mode_writes_override_to_project_settings(capsys):
    _handle_init_and_register(["sess-mode-test", "/x"])
    return_code = _handle_set_mode(
        ["sess-mode-test", REVIEWER_MODE_DEFER_UNTIL_FLUSH]
    )
    assert return_code == 0
    settings = load_project_settings("sess-mode-test")
    assert settings.reviewer_mode_override == REVIEWER_MODE_DEFER_UNTIL_FLUSH


def test_set_mode_accepts_each_valid_mode():
    _handle_init_and_register(["sess-each-mode", "/x"])
    for mode in (
        REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
        REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
        REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    ):
        assert _handle_set_mode(["sess-each-mode", mode]) == 0
        assert load_project_settings("sess-each-mode").reviewer_mode_override == mode


def test_set_mode_rejects_invalid_mode_string():
    _handle_init_and_register(["sess-invalid-mode", "/x"])
    return_code = _handle_set_mode(["sess-invalid-mode", "spicy"])
    assert return_code == 2


def test_set_mode_rejects_wrong_argv_count():
    # set-mode takes exactly one arg (the mode); the project is resolved, not passed.
    # Here the project is given explicitly (it names a real project) plus too many
    # trailing args -> usage error.
    _handle_init_and_register(["sess-count", "/x"])
    return_code = _handle_set_mode(["sess-count", "live", "extra"])
    assert return_code == 2
