"""The UserPromptSubmit hook must fire ONLY when the active session is a member of
some ~/.source-of-truth/projects/*/project-settings.json. An unregistered session
must silently emit exactly `{}` and touch nothing -- there is no opt-out/exempt
file. These tests lock that gate in so the exempt-file pattern cannot creep back."""
from __future__ import annotations

import io
import json

from source_of_truth import cli_entrypoint, load_config
from source_of_truth.add_session_to_project_cli import add_session_to_project


def _run_user_prompt_submit(session_id, transcript_path, prompt, monkeypatch):
    payload = json.dumps({
        "session_id": session_id,
        "transcript_path": str(transcript_path),
        "prompt": prompt,
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return cli_entrypoint._handle_user_prompt_submit_hook()


def test_unregistered_session_emits_empty_object_and_touches_nothing(tmp_path, monkeypatch, capsys):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n"
    )

    exit_code = _run_user_prompt_submit("session-not-in-any-project", transcript, "hello", monkeypatch)

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "{}"
    # No project directory was created for the unregistered session.
    assert not load_config.project_directory_for("session-not-in-any-project").exists()


def test_registered_session_emits_additional_context(tmp_path, monkeypatch, capsys):
    project_id = session_id = "registered-sess"
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "first"}}) + "\n"
    )
    add_session_to_project(project_id, session_id, str(transcript))

    exit_code = _run_user_prompt_submit(session_id, transcript, "first", monkeypatch)

    assert exit_code == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert emitted["hookSpecificOutput"]["additionalContext"]
