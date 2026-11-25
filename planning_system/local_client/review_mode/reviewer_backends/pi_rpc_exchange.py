"""Private: one prompt over pi's RPC protocol (`pi --mode rpc`): a JSONL `prompt` command on stdin, then read
the LF-delimited event stream until `agent_end`. The final text is the last `turn_end` message's text blocks
(same reading as Unharness's PiOutputEventNormalizer). One process per exchange, always cleaned up."""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
import uuid
from typing import Mapping, Optional, Sequence

from ..types import ReviewerUnavailable

_END_OF_STREAM = None


def run_pi_prompt(command: Sequence[str], environment: Mapping[str, str], prompt: str,
                  timeout_seconds: float) -> str:
    try:
        process = subprocess.Popen(list(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=dict(environment), text=True, bufsize=1)
    except OSError as error:
        raise ReviewerUnavailable(f"pi could not start: {error}") from error
    lines: "queue.Queue[Optional[str]]" = queue.Queue()
    threading.Thread(target=_pump, args=(process.stdout, lines), daemon=True).start()
    try:
        prompt_id = uuid.uuid4().hex
        _write(process, {"id": prompt_id, "type": "prompt", "message": prompt})
        return _read_until_agent_end(process, lines, prompt_id, time.monotonic() + timeout_seconds)
    finally:
        _shut_down(process)


def _pump(stream, lines: "queue.Queue[Optional[str]]") -> None:
    for line in stream:
        lines.put(line)
    lines.put(_END_OF_STREAM)


def _write(process: subprocess.Popen, command: dict) -> None:
    try:
        process.stdin.write(json.dumps(command) + "\n")
        process.stdin.flush()
    except (BrokenPipeError, ValueError, OSError) as error:
        raise ReviewerUnavailable(f"pi stdin closed: {error}") from error


def _read_until_agent_end(process, lines, prompt_id: str, deadline: float) -> str:
    final_text = ""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReviewerUnavailable("pi timed out")
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty:
            raise ReviewerUnavailable("pi timed out") from None
        if line is _END_OF_STREAM:
            raise ReviewerUnavailable(f"pi exited before agent_end (exit code {process.poll()})")
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue                                   # non-protocol output; ignore
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "response" and event.get("command") == "prompt" and event.get("success") is False:
            raise ReviewerUnavailable(f"pi refused the prompt: {event.get('error')}")
        if kind == "turn_end":
            text = _message_text(event.get("message"))
            final_text = text or final_text
        if kind == "agent_end":
            return final_text


def _message_text(message) -> str:
    if not isinstance(message, dict):
        return ""
    return "".join(block.get("text", "") for block in message.get("content") or ()
                   if isinstance(block, dict) and block.get("type") == "text")


def _shut_down(process: subprocess.Popen) -> None:
    try:
        process.stdin.close()
    except OSError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
