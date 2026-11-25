"""PostToolUse:AskUserQuestion capture hook: an answered AskUserQuestion mints one
raw_input_log entry per question (answer = submission, question = pre-text) and hands
the new raw_input_id(s) back via additionalContext. Non-answers / unregistered /
non-AUQ tools are silent no-ops. Payload shape mirrors the real PostToolUse stdin."""
from __future__ import annotations

import io
import json

from source_of_truth import post_tool_use_capture_askuserquestion_answers as capture
from source_of_truth import load_config
from source_of_truth.add_session_to_project_cli import add_session_to_project


def _answered_payload(session_id):
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {"question": "Which backend stack?", "header": "Stack", "multiSelect": False,
                 "options": [{"label": "MERN", "description": "x"}, {"label": "Django", "description": "y"}]},
                {"question": "Which features?", "header": "Features", "multiSelect": True,
                 "options": [{"label": "Auth", "description": "x"}, {"label": "Search", "description": "y"}]},
            ],
            "answers": {
                "Which backend stack?": "MERN",
                "Which features?": "Auth, Search",
            },
        },
        "tool_response": {"answers": {"Which backend stack?": "MERN", "Which features?": "Auth, Search"}},
    }


def _run(payload, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = capture._main()
    out = capsys.readouterr().out
    return rc, json.loads(out)


def test_answered_appends_one_entry_per_question_and_returns_ids(tmp_path, monkeypatch, capsys):
    project_id = session_id = "sess-auq"
    add_session_to_project(project_id, session_id, "/tmp/t.jsonl")

    rc, emitted = _run(_answered_payload(session_id), monkeypatch, capsys)
    assert rc == 0

    raw_log = json.loads(load_config.project_raw_input_log_file_path(project_id).read_text())
    entries = raw_log[session_id]
    assert len(entries) == 2  # one per question
    # answer is the submission_text; question is captured as pre-text
    assert entries[0]["submission_text"] == "MERN"
    assert "Which backend stack?" in entries[0]["pre_submission_content"]
    assert entries[1]["submission_text"] == "Auth, Search"  # multiSelect joined

    ctx = emitted["hookSpecificOutput"]["additionalContext"]
    assert "raw_input_id" in ctx
    assert "MERN" in ctx and "Auth, Search" in ctx


def test_unregistered_session_is_silent_noop(tmp_path, monkeypatch, capsys):
    rc, emitted = _run(_answered_payload("not-registered"), monkeypatch, capsys)
    assert rc == 0
    assert emitted == {}
    assert not load_config.project_directory_for("not-registered").exists()


def test_no_answers_is_silent_noop(tmp_path, monkeypatch, capsys):
    project_id = session_id = "sess-noans"
    add_session_to_project(project_id, session_id, "/tmp/t.jsonl")
    payload = _answered_payload(session_id)
    payload["tool_input"]["answers"] = {}
    payload["tool_response"]["answers"] = {}
    rc, emitted = _run(payload, monkeypatch, capsys)
    assert rc == 0
    assert emitted == {}


def test_non_askuserquestion_tool_is_silent_noop(tmp_path, monkeypatch, capsys):
    project_id = session_id = "sess-other"
    add_session_to_project(project_id, session_id, "/tmp/t.jsonl")
    payload = _answered_payload(session_id)
    payload["tool_name"] = "Bash"
    rc, emitted = _run(payload, monkeypatch, capsys)
    assert rc == 0
    assert emitted == {}
