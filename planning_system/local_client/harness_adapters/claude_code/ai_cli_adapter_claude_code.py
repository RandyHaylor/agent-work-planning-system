"""Concrete AiCliAdapter implementation for Anthropic's Claude Code CLI.

Reviewer persistence model:
  - First call uses `claude -p --session-id <uuid> --output-format stream-json
    --include-partial-messages ...` to create the reviewer session with priming.
  - Subsequent calls reuse the session via `claude -p --resume <uuid> ...`.
  - Output is streamed in NDJSON so EVERY event (assistant text deltas, tool
    calls, partial messages, final result) is appended to the reviewer-thinking
    log as it arrives. If the call later times out, we still have the full
    record of what the reviewer was doing.

Tool sandbox: --allowed-tools restricts what the reviewer may invoke.
--add-dir grants Read access to the project directory without permission prompts.
"""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..ai_cli_adapter_interface import (
    AiCliAdapterInterface,
    PersistentReviewerSessionHandle,
)
from ..process_tracker import NoProcessTracking, ProcessTracker
from ..types import HeadlessSessionSpec


STDOUT_EOF_SENTINEL = None


class StreamDeadlineWatch:
    """The per-call deadline and the silent-stream heartbeat, on an injectable monotonic clock (so the
    wait loop's timing is testable without a subprocess)."""

    def __init__(self, timeout_seconds: float, heartbeat_after_silent_seconds: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._heartbeat_after = heartbeat_after_silent_seconds
        started = clock()
        self._deadline = started + timeout_seconds
        self._last_event = started
        self._next_heartbeat = started + heartbeat_after_silent_seconds

    def expired(self) -> bool:
        return self._clock() > self._deadline

    def heartbeat_message(self) -> Optional[str]:
        """A message when a heartbeat is due (then schedules the next one), else None."""
        now = self._clock()
        if now <= self._next_heartbeat:
            return None
        self._next_heartbeat = now + self._heartbeat_after
        return (f"no stream events for {round(now - self._last_event, 1)}s "
                f"(timeout in {round(self._deadline - now, 1)}s)")

    def event_arrived(self) -> None:
        self._last_event = self._clock()
        self._next_heartbeat = self._last_event + self._heartbeat_after


@dataclass
class _StreamOutcome:
    final_result_text: Optional[str] = None
    timed_out: bool = False
    assistant_text_chunks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _PipeReaders:
    stdout_lines: "queue.Queue[Optional[str]]"
    stderr_thread: threading.Thread
    stdout_thread: threading.Thread


class ClaudeCodeReviewerSessionHandleViaResume(PersistentReviewerSessionHandle):
    """Reviewer handle that persists via Claude's --session-id / --resume mechanism.

    Streams every NDJSON event from `claude -p --output-format stream-json`
    to a caller-supplied appender so the reviewer-thinking log captures
    everything in real time -- even if the call later times out.
    """

    def __init__(
        self,
        reviewer_session_id: str,
        allowed_tool_names: list[str],
        allowed_read_paths: list[str],
        priming_already_done: bool,
        reviewer_model_name: str,
        streaming_event_appender: Optional[Callable[[str, str], None]] = None,
        per_call_timeout_seconds: float = 120.0,
        heartbeat_after_silent_seconds: float = 15.0,
        process_tracker: Optional[ProcessTracker] = None,
    ) -> None:
        self._process_tracker = process_tracker or NoProcessTracking()
        self._reviewer_session_id = reviewer_session_id
        self._allowed_tool_names = list(allowed_tool_names)
        self._allowed_read_paths = list(allowed_read_paths)
        self._priming_already_done = priming_already_done
        self._reviewer_model_name = reviewer_model_name
        self._streaming_event_appender = streaming_event_appender
        self._per_call_timeout_seconds = per_call_timeout_seconds
        self._heartbeat_after_silent_seconds = heartbeat_after_silent_seconds
        self._is_alive = True

    @property
    def session_id(self) -> str:
        return self._reviewer_session_id

    def is_alive(self) -> bool:
        return self._is_alive

    def terminate(self) -> None:
        self._is_alive = False

    def _emit_streamed_event(self, event_kind: str, event_body_text: str) -> None:
        if self._streaming_event_appender is not None:
            try:
                self._streaming_event_appender(event_kind, event_body_text)
            except Exception:
                pass

    def _drain_stderr_into_log_until_eof(self, stderr_handle) -> None:
        if stderr_handle is None:
            return
        try:
            for line in iter(stderr_handle.readline, ""):
                stripped = line.rstrip("\n")
                if stripped:
                    self._emit_streamed_event("STDERR_LINE", stripped)
        except Exception:
            pass

    def _handle_stdout_line(
        self, line: str, accumulated_assistant_text_chunks: list[str]
    ) -> Optional[str]:
        """Process one NDJSON line. Returns final result text if this was the result event."""
        stripped = line.rstrip("\n")
        if not stripped:
            return None
        self._emit_streamed_event("STREAM_LINE", stripped)
        try:
            parsed_event = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        event_type = parsed_event.get("type")
        if event_type == "assistant":
            content_blocks = parsed_event.get("message", {}).get("content") or []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_chunk = block.get("text") or ""
                    if text_chunk:
                        accumulated_assistant_text_chunks.append(text_chunk)
        elif event_type == "result":
            self._emit_streamed_event(
                "FINAL_RESULT",
                f"is_error={parsed_event.get('is_error')} "
                f"cost_usd={parsed_event.get('total_cost_usd')}",
            )
            final_text = parsed_event.get("result")
            if not isinstance(final_text, str):
                final_text = "".join(accumulated_assistant_text_chunks)
            return final_text
        return None

    def _build_command(self) -> list[str]:
        command = ["claude", "-p"]
        if self._reviewer_model_name:
            command += ["--model", self._reviewer_model_name]
        command += [
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",  # required by stream-json per claude CLI
        ]
        if self._priming_already_done:
            command += ["--resume", self._reviewer_session_id]
        else:
            command += ["--session-id", self._reviewer_session_id]
        if self._allowed_tool_names:
            command += ["--allowed-tools", ",".join(self._allowed_tool_names)]
        # NOTE: --add-dir is variadic in the claude CLI (`--add-dir <dirs...>`),
        # which would swallow any positional prompt argument that followed it.
        # We therefore pass the prompt via stdin instead of as a positional arg.
        for read_path in self._allowed_read_paths:
            command += ["--add-dir", read_path]
        return command

    def send_prompt_and_await_response(self, prompt_text: str) -> str:
        command = self._build_command()
        self._process_tracker.before_launch()          # a halted client launches nothing (build log #68)
        process_handle = self._launch(command, prompt_text)
        try:
            pipe_readers = self._start_pipe_readers(process_handle)
            try:
                outcome = self._await_result(pipe_readers.stdout_lines, process_handle.kill)
            finally:
                self._stop(process_handle, pipe_readers)
        finally:
            if getattr(process_handle, "pid", None) is not None:
                self._process_tracker.exited(process_handle.pid)
        return self._result_or_fallback(outcome)

    def _launch(self, command: list[str], prompt_text: str) -> "subprocess.Popen[str]":
        """Starts claude in its own process group (so `planning halt` can kill it and whatever it started) and
        pipes the whole prompt to stdin (EOF makes it start)."""
        self._emit_streamed_event(
            "SUBPROCESS_LAUNCH",
            f"session_id={self._reviewer_session_id} "
            f"resume={self._priming_already_done} "
            f"timeout_seconds={self._per_call_timeout_seconds} "
            f"prompt_chars={len(prompt_text)} "
            f"command={json.dumps(command)}",
        )
        process_handle = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        if getattr(process_handle, "pid", None) is not None:
            self._process_tracker.launched(process_handle.pid, f"reviewer {self._reviewer_session_id}")
        try:
            assert process_handle.stdin is not None
            process_handle.stdin.write(prompt_text)
            process_handle.stdin.close()
        except (BrokenPipeError, OSError) as stdin_exc:
            self._emit_streamed_event(
                "STDIN_WRITE_FAILED",
                f"could not pipe prompt to subprocess: {stdin_exc}",
            )
        self._priming_already_done = True
        return process_handle

    def _start_pipe_readers(self, process_handle) -> "_PipeReaders":
        """stderr is drained into the log (a full pipe would deadlock the child); stdout lines go onto a
        queue the wait loop polls with a timeout, so it can also check the deadline (cross-platform;
        select() on pipes is Linux/macOS only). The queue ends with STDOUT_EOF_SENTINEL."""
        stderr_drainer_thread = threading.Thread(
            target=self._drain_stderr_into_log_until_eof,
            args=(process_handle.stderr,),
            daemon=True,
        )
        stderr_drainer_thread.start()
        stdout_line_queue: "queue.Queue[Optional[str]]" = queue.Queue()

        def stdout_reader_into_queue() -> None:
            try:
                assert process_handle.stdout is not None
                for line in iter(process_handle.stdout.readline, ""):
                    stdout_line_queue.put(line)
            finally:
                stdout_line_queue.put(STDOUT_EOF_SENTINEL)

        stdout_reader_thread = threading.Thread(target=stdout_reader_into_queue, daemon=True)
        stdout_reader_thread.start()
        return _PipeReaders(stdout_line_queue, stderr_drainer_thread, stdout_reader_thread)

    def _await_result(self, stdout_lines: "queue.Queue[Optional[str]]",
                      kill: Callable[[], None]) -> "_StreamOutcome":
        """Reads stream lines until the result event, EOF or the deadline (then kills the process),
        logging a heartbeat whenever the stream has been silent too long."""
        watch = StreamDeadlineWatch(self._per_call_timeout_seconds, self._heartbeat_after_silent_seconds)
        outcome = _StreamOutcome()
        while True:
            if watch.expired():
                outcome.timed_out = True
                self._emit_streamed_event(
                    "TIMEOUT",
                    f"per_call_timeout_seconds={self._per_call_timeout_seconds} "
                    f"exceeded; killing subprocess",
                )
                kill()
                return outcome
            heartbeat = watch.heartbeat_message()
            if heartbeat is not None:
                self._emit_streamed_event("WAITING_FOR_EVENT", heartbeat)
            try:
                queued_line = stdout_lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if queued_line is STDOUT_EOF_SENTINEL:
                return outcome
            watch.event_arrived()
            final_text = self._handle_stdout_line(queued_line, outcome.assistant_text_chunks)
            if final_text is not None:
                outcome.final_result_text = final_text
                return outcome

    @staticmethod
    def _stop(process_handle, pipe_readers: "_PipeReaders") -> None:
        if process_handle.poll() is None:
            try:
                os.killpg(process_handle.pid, signal.SIGKILL)    # its own group: anything it started goes too
            except (OSError, AttributeError):
                try:
                    process_handle.kill()
                except OSError:
                    pass
        pipe_readers.stderr_thread.join(timeout=2.0)
        pipe_readers.stdout_thread.join(timeout=2.0)

    def _result_or_fallback(self, outcome: "_StreamOutcome") -> str:
        if outcome.timed_out:
            return (
                f"[reviewer subprocess timed out after {self._per_call_timeout_seconds}s; "
                f"see streamed events in the reviewer log]"
            )
        if outcome.final_result_text is not None:
            return outcome.final_result_text
        return "".join(outcome.assistant_text_chunks) or "[reviewer subprocess produced no parsable output]"


class ClaudeCodeAdapter(AiCliAdapterInterface):
    def __init__(self, current_session_id: str | None = None,
                 session_logs_directory: "Path | None" = None,
                 process_tracker: Optional[ProcessTracker] = None) -> None:
        self._current_session_id = current_session_id or os.environ.get(
            "CLAUDE_SESSION_ID", "unknown-session"
        )
        self._session_logs_directory = Path(session_logs_directory or tempfile.gettempdir())
        self._process_tracker = process_tracker

    def get_current_session_id(self) -> str:
        return self._current_session_id

    def register_user_prompt_submit_hook(
        self, hook_callable: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        # Claude Code hooks are registered declaratively in settings.json.
        # The adapter just keeps the callable for cli_entrypoint to dispatch.
        self._user_prompt_submit_hook_callable = hook_callable

    def inject_into_next_user_turn(self, injection_text: str) -> None:
        self._pending_next_turn_injection = injection_text

    def inject_into_subagent_spawn(self, injection_text: str) -> None:
        self._pending_subagent_spawn_injection = injection_text

    def spawn_persistent_reviewer_session(
        self,
        priming_prompt_text: str,
        allowed_read_paths: list[str],
        allowed_tool_names: list[str],
        reviewer_model_name: str,
        streaming_event_appender: Optional[Callable[[str, str], None]] = None,
    ) -> PersistentReviewerSessionHandle:
        new_reviewer_session_id = str(uuid.uuid4())
        handle = ClaudeCodeReviewerSessionHandleViaResume(
            reviewer_session_id=new_reviewer_session_id,
            allowed_tool_names=allowed_tool_names,
            allowed_read_paths=allowed_read_paths,
            priming_already_done=False,
            reviewer_model_name=reviewer_model_name,
            streaming_event_appender=streaming_event_appender,
            process_tracker=self._process_tracker,
        )
        # Planning system: the reviewer answers free-form questions (05-spec-review-dispatch.md), so the
        # caller's priming text is sent as-is (SoT's JSON change-set verdict format is dropped).
        priming_payload = priming_prompt_text
        if allowed_read_paths:
            priming_payload += f"\nAllowed read paths: {allowed_read_paths}"
        handle.send_prompt_and_await_response(priming_payload)
        return handle

    def spawn_headless_session(
        self, spec: HeadlessSessionSpec
    ) -> PersistentReviewerSessionHandle:
        """Planning system addition: a `claude -p` session handle (stream-json, --session-id then --resume,
        prompt on stdin) running in spec.working_directory with spec.environment. The claude process is
        detached and writes to a log file, so it outlives the `planning` command that started it."""
        from .headless_session_handle import ClaudeCodeHeadlessSessionHandle

        return ClaudeCodeHeadlessSessionHandle(spec, self._session_logs_directory)
