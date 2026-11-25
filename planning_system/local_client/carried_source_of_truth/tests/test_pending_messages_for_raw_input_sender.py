from __future__ import annotations

import io
import json

from source_of_truth.load_config import SOURCE_OF_TRUTH_ROOT_DIR, save_project_settings, load_project_settings
from source_of_truth.pending_messages_for_raw_input_sender import (
    add_pending_message_for_raw_input_sender,
    show_pending_messages_to_raw_input_sender_for_project,
)


def _register_session_under_project(project_id: str, session_id: str) -> None:
    settings = load_project_settings(project_id)
    settings.member_sessions.append({"session_id": session_id, "conversation_path": "/x"})
    save_project_settings(settings)


def test_drain_returns_only_messages_for_target_project_and_keeps_others():
    add_pending_message_for_raw_input_sender("for-alpha-1", target_project_id="alpha")
    add_pending_message_for_raw_input_sender("for-beta-1", target_project_id="beta")
    add_pending_message_for_raw_input_sender("for-alpha-2", target_project_id="alpha")

    alpha_drained = show_pending_messages_to_raw_input_sender_for_project("alpha")
    assert [m["message_text"] for m in alpha_drained] == ["for-alpha-1", "for-alpha-2"]

    # Beta's message remains queued.
    beta_drained = show_pending_messages_to_raw_input_sender_for_project("beta")
    assert [m["message_text"] for m in beta_drained] == ["for-beta-1"]

    # Both queues now empty.
    assert show_pending_messages_to_raw_input_sender_for_project("alpha") == []
    assert show_pending_messages_to_raw_input_sender_for_project("beta") == []


def test_drain_handles_missing_file():
    queue_file = SOURCE_OF_TRUTH_ROOT_DIR / "pending_user_messages.jsonl"
    if queue_file.exists():
        queue_file.unlink()
    assert show_pending_messages_to_raw_input_sender_for_project("anything") == []


def test_emitter_emits_systemMessage_only_for_matching_session(monkeypatch, capsys):
    _register_session_under_project("alpha", "sess-A")
    _register_session_under_project("beta", "sess-B")
    add_pending_message_for_raw_input_sender("hello-alpha", target_project_id="alpha")
    add_pending_message_for_raw_input_sender("hello-beta", target_project_id="beta")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": "sess-A"})))
    from source_of_truth.post_tool_use_show_messages_to_raw_input_sender import _main as emit_main
    assert emit_main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "systemMessage" in payload
    assert "hello-alpha" in payload["systemMessage"]
    assert "hello-beta" not in payload["systemMessage"]

    # Beta's message remains queued for its session.
    remaining_beta = show_pending_messages_to_raw_input_sender_for_project("beta")
    assert [m["message_text"] for m in remaining_beta] == ["hello-beta"]


def test_emitter_outputs_empty_object_for_unregistered_session(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": "stranger"})))
    from source_of_truth.post_tool_use_show_messages_to_raw_input_sender import _main as emit_main
    assert emit_main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {}


def test_emitter_outputs_empty_object_when_no_session_id_in_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    from source_of_truth.post_tool_use_show_messages_to_raw_input_sender import _main as emit_main
    assert emit_main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {}
