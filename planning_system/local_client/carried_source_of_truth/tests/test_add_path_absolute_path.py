"""add-path must accept an absolute filesystem path. Regression for the bug where
_resolve_project_and_remaining_args misread an absolute path as a positional
project-id override (pathlib's `/` collapses an absolute right operand, so
project_directory_for('/abs') returns '/abs', which often exists)."""
from __future__ import annotations

from source_of_truth import cli_entrypoint
from source_of_truth.add_session_to_project_cli import add_session_to_project


def _register_session(monkeypatch, project_and_session_id="sess-addpath"):
    add_session_to_project(project_and_session_id, project_and_session_id, "/tmp/t.jsonl")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", project_and_session_id)
    return project_and_session_id


def test_resolver_does_not_consume_absolute_path_argument(tmp_path, monkeypatch):
    project_id = _register_session(monkeypatch)
    abs_dir = str(tmp_path)  # an absolute path that exists
    resolved_project, remaining, error = cli_entrypoint._resolve_project_and_remaining_args([abs_dir])
    assert error is None
    assert resolved_project == project_id
    assert remaining == [abs_dir]  # the path was NOT swallowed as a project override


def test_add_path_with_absolute_existing_path_succeeds(tmp_path, monkeypatch, capsys):
    _register_session(monkeypatch)
    abs_dir = str(tmp_path)
    rc = cli_entrypoint._handle_add_path([abs_dir])
    assert rc == 0
    assert capsys.readouterr().out.strip() in {"added", "already_present"}


def test_add_path_nonexistent_path_returns_clean_error_no_traceback(tmp_path, monkeypatch, capsys):
    _register_session(monkeypatch)
    missing = str(tmp_path / "does-not-exist")
    rc = cli_entrypoint._handle_add_path([missing])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err  # clean message, not a raw traceback
    assert "non-existent" in captured.err.lower() or "does not exist" in captured.err.lower()
