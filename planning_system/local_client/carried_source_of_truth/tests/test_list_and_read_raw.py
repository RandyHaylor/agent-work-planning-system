"""list-raw shows each raw-log entry as `raw-<id>: <first 30 chars>`; read-raw
prints one entry in full and accepts a bare or `raw-`-prefixed id."""
from __future__ import annotations

import json

from source_of_truth import cli_entrypoint
from source_of_truth.add_session_to_project_cli import add_session_to_project
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log


def _register(monkeypatch, project_and_session="sess-raw"):
    add_session_to_project(project_and_session, project_and_session, "/tmp/t.jsonl")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", project_and_session)
    return project_and_session


def test_list_raw_previews_first_30_chars(monkeypatch, capsys):
    project_id = _register(monkeypatch)
    append_submission_to_raw_input_log(project_id, project_id, "short answer", "")
    long_text = "this is a very long submission that definitely exceeds thirty characters"
    append_submission_to_raw_input_log(project_id, project_id, long_text, "")

    rc = cli_entrypoint._handle_list_raw([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "raw-0: short answer" in out
    assert "raw-1: " + long_text[:30] in out
    assert "…" in out  # long one is truncated with an ellipsis
    # preview never includes the full long text
    assert long_text not in out


def test_list_raw_empty(monkeypatch, capsys):
    _register(monkeypatch, "sess-empty")
    rc = cli_entrypoint._handle_list_raw([])
    assert rc == 0
    assert "no raw input log entries" in capsys.readouterr().out


def test_read_raw_full_entry_accepts_prefixed_and_bare(monkeypatch, capsys):
    project_id = _register(monkeypatch)
    append_submission_to_raw_input_log(project_id, project_id, "the full text here", "prior agent turn")

    rc = cli_entrypoint._handle_read_raw(["raw-0"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["raw_input_id"] == "raw-0"
    assert payload["submission_text"] == "the full text here"
    assert payload["pre_submission_content"] == "prior agent turn"

    rc_bare = cli_entrypoint._handle_read_raw(["0"])  # bare also works
    assert rc_bare == 0
    assert json.loads(capsys.readouterr().out)["submission_text"] == "the full text here"


def test_read_raw_missing_id_returns_error(monkeypatch, capsys):
    _register(monkeypatch, "sess-missing")
    rc = cli_entrypoint._handle_read_raw(["raw-999"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err
