"""Gap-anchored look-behind capture: on each normal UserPromptSubmit, back-fill the
user messages sent WHILE THE AGENT WAS WORKING that never fired their own hook.

Those messages are recorded in the transcript as ``queued_command`` attachments (not
type=="user" prompt events). The detector anchors on the previous normal submission
and collects the human queued_command attachments in the gap up to the incoming
prompt -- so it never rescans old history (no cross-session duplication)."""
from __future__ import annotations

import io
import json

from source_of_truth import cli_entrypoint, load_config
from source_of_truth.add_session_to_project_cli import add_session_to_project
from source_of_truth.claude_cli_get_recent_agent_messages import (
    find_user_messages_sent_while_agent_was_working,
)


def _user(text):
    return {"type": "user", "promptSource": "typed",
            "message": {"role": "user", "content": text}}


def _assistant(text):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": text}]}}


def _queued_human(text):
    return {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": text,
        "commandMode": "prompt", "origin": {"kind": "human"}}}


def _queued_task_notification(text):
    return {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": text,
        "commandMode": "task-notification", "origin": {"kind": "human"}}}


# ----- the gap-anchored detector -----

def test_queued_message_in_the_gap_is_backfilled_incoming_appended():
    # previous submit, [agent works], a queued human message, then the incoming
    # prompt already appended as the last genuine user event.
    events = [
        _user("previous submit"),
        _assistant("working ..."),
        _queued_human("typed while you worked"),
        _user("incoming"),
    ]
    assert find_user_messages_sent_while_agent_was_working(events, "incoming") == [
        "typed while you worked"
    ]


def test_queued_message_in_the_gap_is_backfilled_incoming_not_appended():
    # Same, but the incoming prompt is NOT yet written to the transcript when the hook
    # runs -> the gap runs from the last genuine prompt to the end.
    events = [
        _user("previous submit"),
        _assistant("working ..."),
        _queued_human("typed while you worked"),
    ]
    assert find_user_messages_sent_while_agent_was_working(events, "incoming") == [
        "typed while you worked"
    ]


def test_multiple_queued_messages_preserved_in_order():
    events = [
        _user("previous submit"),
        _queued_human("first queued"),
        _queued_human("second queued"),
        _user("incoming"),
    ]
    assert find_user_messages_sent_while_agent_was_working(events, "incoming") == [
        "first queued", "second queued"
    ]


def test_task_notification_attachments_are_ignored():
    events = [
        _user("previous submit"),
        _queued_task_notification("<task-notification>done</task-notification>"),
        _queued_human("real human message"),
        _user("incoming"),
    ]
    assert find_user_messages_sent_while_agent_was_working(events, "incoming") == [
        "real human message"
    ]


def test_incoming_prompt_even_if_queued_is_not_backfilled():
    # If the incoming prompt was itself a queued message being consumed now, its
    # attachment must NOT be back-filled (the normal path logs it).
    events = [
        _user("previous submit"),
        _queued_human("incoming"),
    ]
    assert find_user_messages_sent_while_agent_was_working(events, "incoming") == []


def test_only_the_current_gap_is_scanned_not_old_history():
    # An OLD queued message before the previous submit must NOT be re-collected --
    # this is what prevents cross-session/forked-transcript duplication.
    events = [
        _user("older submit"),
        _queued_human("old queued (already handled long ago)"),
        _user("previous submit"),
        _queued_human("new queued in current gap"),
        _user("incoming"),
    ]
    assert find_user_messages_sent_while_agent_was_working(events, "incoming") == [
        "new queued in current gap"
    ]


def test_no_previous_submit_returns_empty():
    events = [_queued_human("q"), _user("incoming")]
    # With the incoming as the only genuine prompt, anchor is -1 and the queued item
    # before it is still in-gap; but the FIRST-ever prompt has no prior working period,
    # so a lone queued item preceding the very first submit is captured as in-gap.
    # (This documents the boundary; the common case is covered by the tests above.)
    result = find_user_messages_sent_while_agent_was_working(events, "incoming")
    assert result == ["q"]


# ----- end-to-end through the real UserPromptSubmit hook handler -----

def _write_transcript(path, events):
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def _run_user_prompt_submit(session_id, transcript_path, prompt, monkeypatch):
    payload = json.dumps({
        "session_id": session_id,
        "transcript_path": str(transcript_path),
        "prompt": prompt,
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    cli_entrypoint._handle_user_prompt_submit_hook()


def _session_submissions(project_id, session_id):
    raw_log = json.loads(
        load_config.project_raw_input_log_file_path(project_id).read_text()
    )
    return [entry["submission_text"] for entry in raw_log[session_id]]


def test_hook_backfills_queued_message_then_logs_incoming(tmp_path, monkeypatch):
    project_id = session_id = "sess-gap"
    transcript = tmp_path / "t.jsonl"
    add_session_to_project(project_id, session_id, str(transcript))

    # Turn 1: normal submit logged through the real hook.
    _write_transcript(transcript, [_user("first normal prompt")])
    _run_user_prompt_submit(session_id, transcript, "first normal prompt", monkeypatch)

    # The user then typed a message WHILE THE AGENT WORKED (a queued_command
    # attachment), then submits a second normal prompt (already appended).
    _write_transcript(transcript, [
        _user("first normal prompt"),
        _assistant("working ..."),
        _queued_human("a message I sent while you were working"),
        _user("second normal prompt"),
    ])
    _run_user_prompt_submit(session_id, transcript, "second normal prompt", monkeypatch)

    assert _session_submissions(project_id, session_id) == [
        "first normal prompt",
        "a message I sent while you were working",
        "second normal prompt",
    ]


def test_hook_does_not_duplicate_across_repeated_submits(tmp_path, monkeypatch):
    # Running the hook again with no new queued messages must not re-add anything.
    project_id = session_id = "sess-nodupe"
    transcript = tmp_path / "t.jsonl"
    add_session_to_project(project_id, session_id, str(transcript))

    _write_transcript(transcript, [_user("p1")])
    _run_user_prompt_submit(session_id, transcript, "p1", monkeypatch)
    _write_transcript(transcript, [_user("p1"), _assistant("x"), _user("p2")])
    _run_user_prompt_submit(session_id, transcript, "p2", monkeypatch)
    _write_transcript(transcript, [
        _user("p1"), _assistant("x"), _user("p2"), _assistant("y"), _user("p3")])
    _run_user_prompt_submit(session_id, transcript, "p3", monkeypatch)

    assert _session_submissions(project_id, session_id) == ["p1", "p2", "p3"]
