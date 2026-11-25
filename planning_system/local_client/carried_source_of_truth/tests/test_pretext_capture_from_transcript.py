"""Pre-text capture: the UserPromptSubmit hook reads the agent's PRECEDING turn
straight from the session transcript.

This replaces the old Stop-hook handoff, which silently lost the pre-text
whenever the user interrupted/canceled a turn (no Stop event fires on cancel).
Reading the transcript at submit time captures the preceding turn every prompt,
including its partial output when interrupted."""
from __future__ import annotations

import io
import json

from source_of_truth import cli_entrypoint, load_config
from source_of_truth.add_session_to_project_cli import add_session_to_project
from source_of_truth.claude_cli_get_recent_agent_messages import (
    build_pre_text_for_incoming_user_prompt,
)

# A completed turn: user prompt, assistant text, assistant tool_use, tool_result
# (recorded as type:user), assistant closing text.
PRECEDING_TURN_EVENTS = [
    {"type": "user", "message": {"role": "user", "content": "design the audio thing"}},
    {"type": "assistant", "message": {"role": "assistant",
        "content": [{"type": "text", "text": "Here is the plan: A, B, C."}]}},
    {"type": "assistant", "message": {"role": "assistant",
        "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}},
    {"type": "user", "message": {"role": "user",
        "content": [{"type": "tool_result", "content": "file1 file2"}]}},
    {"type": "assistant", "message": {"role": "assistant",
        "content": [{"type": "text", "text": "Done; confirm?"}]}},
]


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


def _last_entry(project_id, session_id):
    raw_log = json.loads(load_config.project_raw_input_log_file_path(project_id).read_text())
    return raw_log[session_id][-1]


# ----- extractor unit tests: robust to BOTH hook-timing orderings -----

def test_extractor_when_incoming_prompt_not_yet_in_transcript():
    # Transcript ends with the agent turn; the new "yes" is NOT appended yet.
    pre = build_pre_text_for_incoming_user_prompt(PRECEDING_TURN_EVENTS, "yes")
    assert "Here is the plan: A, B, C." in pre
    assert "Done; confirm?" in pre
    assert "[tool_result] file1 file2" in pre   # tool RESULT included
    assert "[tool:" not in pre                  # tool CALL excluded


def test_extractor_when_incoming_prompt_already_appended():
    # Same turn, but the new "yes" prompt is already written to the transcript.
    events = PRECEDING_TURN_EVENTS + [
        {"type": "user", "message": {"role": "user", "content": "yes"}},
    ]
    pre = build_pre_text_for_incoming_user_prompt(events, "yes")
    assert "Here is the plan: A, B, C." in pre
    assert "Done; confirm?" in pre
    assert "[tool_result] file1 file2" in pre


def test_extractor_first_prompt_has_no_preceding_turn():
    events = [{"type": "user", "message": {"role": "user", "content": "first"}}]
    assert build_pre_text_for_incoming_user_prompt(events, "first") == ""
    assert build_pre_text_for_incoming_user_prompt([], "first") == ""


# ----- end-to-end through the UserPromptSubmit hook -----

def test_userpromptsubmit_captures_preceding_turn_as_pretext(tmp_path, monkeypatch):
    project_id = session_id = "sess-x"
    transcript = tmp_path / "t.jsonl"
    add_session_to_project(project_id, session_id, str(transcript))
    _write_transcript(transcript, PRECEDING_TURN_EVENTS)  # "yes" not yet appended

    _run_user_prompt_submit(session_id, transcript, "yes", monkeypatch)

    entry = _last_entry(project_id, session_id)
    assert entry["submission_text"] == "yes"
    assert "Here is the plan: A, B, C." in entry["pre_submission_content"]
    assert "[tool_result] file1 file2" in entry["pre_submission_content"]


def test_userpromptsubmit_interrupted_turn_still_captures_partial_output(tmp_path, monkeypatch):
    # Interrupted turn: agent emitted text then a tool_use, but never a closing
    # message (no Stop event would have fired). Partial text is still captured
    # because we read the transcript at submit time -- the bug this fix targets.
    interrupted = [
        {"type": "user", "message": {"role": "user", "content": "do the thing"}},
        {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": "Working on it; should I use X?"}]}},
    ]
    project_id = session_id = "sess-int"
    transcript = tmp_path / "i.jsonl"
    add_session_to_project(project_id, session_id, str(transcript))
    _write_transcript(transcript, interrupted)

    _run_user_prompt_submit(session_id, transcript, "yes", monkeypatch)

    entry = _last_entry(project_id, session_id)
    assert entry["submission_text"] == "yes"
    assert "Working on it; should I use X?" in entry["pre_submission_content"]


# ----- interrupted/canceled turn: the transcript contains a synthetic
# "[Request interrupted by user]" marker (type==user) between the agent's
# partial output and the next real prompt. The boundary logic must skip it so
# the preceding agent output is still captured (not blocked) AND the marker text
# must never leak into the captured pre-text (not corrupted). -----

INTERRUPTED_TURN_WITH_CANCEL_MARKER = [
    {"type": "user", "message": {"role": "user", "content": "do the big task"}},
    {"type": "assistant", "message": {"role": "assistant",
        "content": [{"type": "text", "text": "Starting; I edited file A."}]}},
    {"type": "assistant", "message": {"role": "assistant",
        "content": [{"type": "tool_use", "name": "Edit", "input": {}}]}},
    {"type": "user", "message": {"role": "user",
        "content": [{"type": "tool_result", "content": "edited A"}]}},
    {"type": "assistant", "message": {"role": "assistant",
        "content": [{"type": "text", "text": "Now doing B..."}]}},
    {"type": "user", "message": {"role": "user", "content": "[Request interrupted by user]"}},
]


def test_cancel_marker_is_not_a_genuine_user_prompt():
    from source_of_truth.claude_cli_get_recent_agent_messages import _is_genuine_user_prompt
    marker_event = {"type": "user", "message": {"role": "user", "content": "[Request interrupted by user]"}}
    tool_use_variant = {"type": "user", "message": {"role": "user", "content": "[Request interrupted by user for tool use]"}}
    real_prompt = {"type": "user", "message": {"role": "user", "content": "do the big task"}}
    assert _is_genuine_user_prompt(marker_event) is False
    assert _is_genuine_user_prompt(tool_use_variant) is False
    assert _is_genuine_user_prompt(real_prompt) is True


def test_interrupted_turn_pretext_not_blocked_and_not_corrupted_marker_not_appended():
    # Hook fires with the new prompt NOT yet appended; transcript ends at marker.
    pre = build_pre_text_for_incoming_user_prompt(
        INTERRUPTED_TURN_WITH_CANCEL_MARKER, "actually stop, do C instead"
    )
    assert "Starting; I edited file A." in pre   # output BEFORE the marker captured
    assert "Now doing B..." in pre               # last partial line captured
    assert "[tool_result] edited A" in pre       # tool result captured
    assert "[Request interrupted by user]" not in pre  # marker text NOT leaked


def test_interrupted_turn_pretext_when_new_prompt_already_appended():
    events = INTERRUPTED_TURN_WITH_CANCEL_MARKER + [
        {"type": "user", "message": {"role": "user", "content": "actually stop, do C instead"}},
    ]
    pre = build_pre_text_for_incoming_user_prompt(events, "actually stop, do C instead")
    assert "Starting; I edited file A." in pre
    assert "Now doing B..." in pre
    assert "[Request interrupted by user]" not in pre


def test_userpromptsubmit_first_prompt_has_empty_pretext(tmp_path, monkeypatch):
    project_id = session_id = "sess-y"
    transcript = tmp_path / "y.jsonl"
    add_session_to_project(project_id, session_id, str(transcript))
    _write_transcript(transcript, [
        {"type": "user", "message": {"role": "user", "content": "first message"}},
    ])
    _run_user_prompt_submit(session_id, transcript, "first message", monkeypatch)
    assert _last_entry(project_id, session_id)["pre_submission_content"] == ""
