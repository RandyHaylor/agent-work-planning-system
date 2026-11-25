"""Headless task session for Claude Code (planning system addition to the carried adapter).

Same command line as the reviewer handle (`claude -p`, stream-json, --session-id then --resume, prompt on
stdin) but:
  - runs in the task's working directory with the task's environment (PLANNING_URL / PLANNING_TOKEN /
    PLANNING_CA_CERT layered over this process's environment, so PATH and HOME still resolve);
  - the claude process is detached (own process group) and writes its NDJSON to a log file, so it keeps
    running after the `planning task start` command exits;
  - no per-call timeout (a task can run for a long time); terminate() kills the process group.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from ..types import HeadlessSessionSpec
from .ai_cli_adapter_claude_code import ClaudeCodeReviewerSessionHandleViaResume

POLL_SECONDS = 0.2


class ClaudeCodeHeadlessSessionHandle(ClaudeCodeReviewerSessionHandleViaResume):

    def __init__(self, spec: HeadlessSessionSpec, session_logs_directory: Path):
        super().__init__(
            reviewer_session_id=spec.session_id,
            allowed_tool_names=list(spec.allowed_tools),
            allowed_read_paths=[str(path) for path in spec.allowed_read_paths],
            priming_already_done=False,
            reviewer_model_name=spec.model or "",
        )
        self._working_directory = str(spec.working_directory)
        self._environment = {**os.environ, **dict(spec.environment)}
        self._log_path = Path(session_logs_directory) / f"{spec.session_id}.ndjson"
        self._process: Optional[subprocess.Popen] = None

    @property
    def pid(self) -> Optional[int]:
        """Set once the prompt has been handed to the claude process."""
        return self._process.pid if self._process is not None else None

    @property
    def log_path(self) -> Path:
        return self._log_path

    def is_alive(self) -> bool:
        return self._is_alive

    def terminate(self) -> None:
        self._is_alive = False
        if self._process is not None and self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except (OSError, AttributeError):
                self._process.terminate()

    def send_prompt_and_await_response(self, prompt_text: str) -> str:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        start_offset = self._log_path.stat().st_size if self._log_path.exists() else 0
        with open(self._log_path, "a", encoding="utf-8") as log_stream:
            process = subprocess.Popen(
                self._build_command(), stdin=subprocess.PIPE, stdout=log_stream, stderr=log_stream,
                cwd=self._working_directory, env=self._environment, text=True, encoding="utf-8",
                start_new_session=True)
        try:
            assert process.stdin is not None
            process.stdin.write(prompt_text)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        self._priming_already_done = True
        self._process = process
        return self._follow_log_until_result(process, start_offset)

    def _follow_log_until_result(self, process: subprocess.Popen, offset: int) -> str:
        chunks: list[str] = []
        buffered = ""
        with open(self._log_path, encoding="utf-8", errors="replace") as log_stream:
            log_stream.seek(offset)
            while True:
                data = log_stream.read()
                if data:
                    buffered += data
                    *lines, buffered = buffered.split("\n")
                    for line in lines:
                        result = self._handle_stdout_line(line, chunks)
                        if result is not None:
                            return result
                    continue
                if process.poll() is not None:
                    tail = log_stream.read()
                    for line in (buffered + tail).split("\n"):
                        result = self._handle_stdout_line(line, chunks)
                        if result is not None:
                            return result
                    return "".join(chunks) or "[session produced no parsable output]"
                time.sleep(POLL_SECONDS)
