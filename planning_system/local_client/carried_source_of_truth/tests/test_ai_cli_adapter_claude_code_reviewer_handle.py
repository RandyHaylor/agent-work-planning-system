"""Unit tests for ClaudeCodeReviewerSessionHandleViaResume.

We do NOT actually launch the claude CLI here. We patch subprocess.Popen with a
fake whose stdout is a real OS-level pipe (so select.select works against it),
preloaded with scripted NDJSON lines.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
from typing import Iterable
from unittest.mock import patch

import pytest

from source_of_truth.ai_cli_adapter_claude_code import (
    ClaudeCodeReviewerSessionHandleViaResume,
)


class _FakePopenWithRealPipeStdout:
    """Stand-in for subprocess.Popen with a real-pipe-backed stdout/stderr.

    select.select in production code requires a real fileno(), so we use os.pipe()
    instead of io.StringIO. We pre-write all scripted lines into the write end,
    then close it so EOF is reached after the test consumes everything.
    """

    def __init__(self, scripted_stdout_lines: Iterable[str]) -> None:
        stdout_read_fd, stdout_write_fd = os.pipe()
        joined_text = "".join(
            line if line.endswith("\n") else line + "\n"
            for line in scripted_stdout_lines
        )
        os.write(stdout_write_fd, joined_text.encode("utf-8"))
        os.close(stdout_write_fd)  # signal EOF to the reader
        self.stdout = os.fdopen(stdout_read_fd, "r", buffering=1)

        stderr_read_fd, stderr_write_fd = os.pipe()
        os.close(stderr_write_fd)  # empty stderr -> immediate EOF
        self.stderr = os.fdopen(stderr_read_fd, "r", buffering=1)

        # stdin is now used by production code to pipe the prompt; capture writes.
        self.stdin = io.StringIO()

        self.kill_was_called = False
        self._terminated = False

    def poll(self):
        # Always report "exited cleanly" so the reader breaks out promptly
        # once stdout EOF is reached.
        return 0

    def kill(self):
        self.kill_was_called = True
        self._terminated = True

    def terminate(self):
        self.kill()


def _build_handle(priming_already_done: bool = False, captured_events: list | None = None):
    captured_events = captured_events if captured_events is not None else []
    appender = lambda kind, body: captured_events.append((kind, body))
    return ClaudeCodeReviewerSessionHandleViaResume(
        reviewer_session_id="11111111-2222-3333-4444-555555555555",
        allowed_tool_names=["Read"],
        allowed_read_paths=["/tmp/example"],
        priming_already_done=priming_already_done,
        reviewer_model_name="claude-haiku-4-5-20251001",
        streaming_event_appender=appender,
        per_call_timeout_seconds=10,
        heartbeat_after_silent_seconds=999,  # disable heartbeat for fast tests
    ), captured_events


def test_first_call_uses_session_id_then_subsequent_calls_use_resume():
    handle, _ = _build_handle(priming_already_done=False)
    captured_command_lines: list[list[str]] = []

    def fake_popen(command_list, **kwargs):
        captured_command_lines.append(list(command_list))
        return _FakePopenWithRealPipeStdout([
            json.dumps({"type": "result", "result": "ok", "is_error": False, "total_cost_usd": 0}),
        ])

    with patch("source_of_truth.ai_cli_adapter_claude_code.subprocess.Popen", side_effect=fake_popen):
        handle.send_prompt_and_await_response("first prompt")
        handle.send_prompt_and_await_response("second prompt")

    first_call_command, second_call_command = captured_command_lines
    assert "--session-id" in first_call_command
    assert "11111111-2222-3333-4444-555555555555" in first_call_command
    assert "--resume" not in first_call_command

    assert "--resume" in second_call_command
    assert "--session-id" not in second_call_command

    for cmd in (first_call_command, second_call_command):
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--include-partial-messages" in cmd
        assert "--model" in cmd
        assert "claude-haiku-4-5-20251001" in cmd
        assert "--allowed-tools" in cmd
        assert "Read" in cmd
        assert "--add-dir" in cmd
        assert "/tmp/example" in cmd
        # The prompt must NOT be a positional argument -- variadic --add-dir
        # would swallow it. Prompt is now piped via stdin instead.
        assert "first prompt" not in cmd
        assert "second prompt" not in cmd


def test_returns_result_text_from_final_result_event():
    handle, _ = _build_handle()
    fake_lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "thinking..."}]}}),
        json.dumps({"type": "result", "result": "the verdict reply", "is_error": False, "total_cost_usd": 0.001}),
    ]
    with patch(
        "source_of_truth.ai_cli_adapter_claude_code.subprocess.Popen",
        side_effect=lambda *a, **k: _FakePopenWithRealPipeStdout(fake_lines),
    ):
        response_text = handle.send_prompt_and_await_response("prompt")
    assert response_text == "the verdict reply"


def test_streaming_appender_receives_every_ndjson_line_and_launch_event():
    handle, captured_events = _build_handle()
    fake_lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "partial reasoning"}]}}),
        json.dumps({"type": "result", "result": "final", "is_error": False, "total_cost_usd": 0}),
    ]
    with patch(
        "source_of_truth.ai_cli_adapter_claude_code.subprocess.Popen",
        side_effect=lambda *a, **k: _FakePopenWithRealPipeStdout(fake_lines),
    ):
        handle.send_prompt_and_await_response("prompt")

    streamed_line_event_bodies = [body for kind, body in captured_events if kind == "STREAM_LINE"]
    assert len(streamed_line_event_bodies) == 3
    assert "init" in streamed_line_event_bodies[0]
    assert "partial reasoning" in streamed_line_event_bodies[1]
    assert "final" in streamed_line_event_bodies[2]

    launch_events = [body for kind, body in captured_events if kind == "SUBPROCESS_LAUNCH"]
    assert len(launch_events) == 1
    assert "command=" in launch_events[0]
    assert "timeout_seconds=" in launch_events[0]

    final_result_event = next(
        (body for kind, body in captured_events if kind == "FINAL_RESULT"), None
    )
    assert final_result_event is not None
    assert "is_error=False" in final_result_event


def test_falls_back_to_concatenated_assistant_text_when_result_field_absent():
    handle, _ = _build_handle()
    fake_lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "alpha "},
            {"type": "text", "text": "beta"}]}}),
        json.dumps({"type": "result", "is_error": False}),
    ]
    with patch(
        "source_of_truth.ai_cli_adapter_claude_code.subprocess.Popen",
        side_effect=lambda *a, **k: _FakePopenWithRealPipeStdout(fake_lines),
    ):
        response_text = handle.send_prompt_and_await_response("prompt")
    assert response_text == "alpha beta"


def test_terminate_marks_handle_not_alive():
    handle, _ = _build_handle(priming_already_done=True)
    assert handle.is_alive() is True
    handle.terminate()
    assert handle.is_alive() is False


def test_heartbeat_event_is_emitted_when_no_stream_events_for_threshold_seconds():
    """Heartbeat fires when stdout is silent past heartbeat_after_silent_seconds."""
    captured_events: list = []
    handle = ClaudeCodeReviewerSessionHandleViaResume(
        reviewer_session_id="x",
        allowed_tool_names=[],
        allowed_read_paths=[],
        priming_already_done=False,
        reviewer_model_name="claude-haiku-4-5-20251001",
        streaming_event_appender=lambda k, b: captured_events.append((k, b)),
        per_call_timeout_seconds=3.0,
        heartbeat_after_silent_seconds=1.0,
    )

    # Fake Popen whose stdout pipe never gets any data and whose poll() reports
    # "still running" so we exit only via timeout.
    class _SilentForeverPopen:
        def __init__(self):
            r, w = os.pipe()  # never writing to w
            self._w = w
            self.stdout = os.fdopen(r, "r", buffering=1)
            r2, w2 = os.pipe()
            self._w2 = w2
            self.stderr = os.fdopen(r2, "r", buffering=1)
            self.stdin = io.StringIO()

        def poll(self):
            return None  # still running

        def kill(self):
            os.close(self._w)
            os.close(self._w2)

    with patch(
        "source_of_truth.ai_cli_adapter_claude_code.subprocess.Popen",
        side_effect=lambda *a, **k: _SilentForeverPopen(),
    ):
        result_text = handle.send_prompt_and_await_response("prompt")

    heartbeat_events = [body for kind, body in captured_events if kind == "WAITING_FOR_EVENT"]
    timeout_events = [body for kind, body in captured_events if kind == "TIMEOUT"]
    assert len(heartbeat_events) >= 1
    assert len(timeout_events) == 1
    assert "timed out" in result_text
