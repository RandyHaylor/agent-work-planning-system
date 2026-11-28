#!/usr/bin/env python3
"""
claude_cli_get_recent_agent_messages.py
========================================

A Claude Code transcript extractor for the assistant's text replies emitted
since the most recent user message. Used by the UserPromptSubmit hook (via
build_pre_text_for_incoming_user_prompt) to capture the preceding turn's output
as the next entry's pre-text. Also runnable standalone as a CLI (see below).

This is a READ-ONLY extractor. It produces output on stdout. It does NOT
make decisions about Claude's flow (no block/continue signaling). Pipe its
output into another script that consumes it and decides what to do.


CLI USAGE
---------

Standalone (for testing, with explicit transcript path):

    python3 claude_cli_get_recent_agent_messages.py \\
        --transcript-path ~/.claude/projects/<encoded-cwd>/<session-id>.jsonl

Hook context (reads JSON payload from stdin per Claude Code's hook contract):

    echo '{"transcript_path": "/path/to/session.jsonl"}' \\
        | python3 claude_cli_get_recent_agent_messages.py

Get raw NDJSON instead of plain text:

    python3 claude_cli_get_recent_agent_messages.py \\
        --transcript-path <path> --json

Include tool calls as one-line summaries (text mode only):

    python3 claude_cli_get_recent_agent_messages.py \\
        --transcript-path <path> --include-tool-calls

Custom separator between messages:

    python3 claude_cli_get_recent_agent_messages.py \\
        --transcript-path <path> --separator "---"


FLAGS
-----

--json
    Emit raw JSON events (NDJSON) for the collected assistant messages
    instead of stripped text. Use when piping to a consumer that wants
    structure.

--include-tool-calls
    In text mode, also emit a compact summary line for each tool_use
    block:  `[tool: <name>] <one-line JSON of input>`. Default omits
    tool calls entirely. Has no effect in --json mode (which already
    preserves everything).

--transcript-path PATH
    Bypass stdin payload reading and use the given path directly. Useful
    for testing the script outside the hook context.

--separator SEP
    String inserted between assistant messages in text mode. Default is
    a single blank line ("\\n\\n"). Use "\\n" for tighter output or a
    custom marker like "---" for downstream parsing.


EXIT CODES
----------

  0 — success; output written to stdout
  1 — usage error or transcript not found
  2 — payload malformed (no transcript_path)


SUGGESTED HOOK WIRING
---------------------

In ~/.claude/settings.json (user scope) or .claude/settings.json (project scope):

    {
      "hooks": {
        "Stop": [
          {
            "hooks": [
              {
                "type": "command",
                "command": "python3 /absolute/path/to/claude_cli_get_recent_agent_messages.py | python3 /absolute/path/to/your_consumer.py"
              }
            ]
          }
        ]
      }
    }

The pipe sends the extractor's stdout into your consumer's stdin. The
consumer is whatever script you write to act on the assistant's last
replies — log them, scan for tokens, ship to a webhook, etc.

Examples of useful consumers:

    # Just log to a file
    ... | tee -a ~/claude-replies.log >/dev/null

    # Look for sentinel tokens (DONE, FEATURE_COMPLETE) on their own line
    ... | grep -xE '(DONE|FEATURE_COMPLETE)' && touch /tmp/turn_done

    # Pipe NDJSON to a Python consumer that parses each event
    python3 claude_cli_get_recent_agent_messages.py --json | python3 my_parser.py


WHY NOT JUST PARSE THE TRANSCRIPT YOURSELF?
-------------------------------------------

You can. This script exists because:

  - It handles the stdin-payload contract correctly (hooks pass a JSON
    object containing `transcript_path`).
  - It correctly defines "replies since the last user message" — there
    can be multiple assistant turns between user messages (tool-use
    loops, continued generation, etc.), and all of them should be
    captured.
  - It strips tool_use, tool_result, and thinking blocks by default,
    leaving only text the assistant emitted toward the user.
  - It's a single-file, stdlib-only utility you can drop in anywhere.


DESIGN NOTES
------------

  - Pure stdlib; no external dependencies.
  - Pipe-friendly: text output is plain text, JSON output is NDJSON.
  - Does NOT modify the transcript or make decisions about the hook flow.
    The hook's exit code from settings.json controls Claude's flow;
    this script's exit code only signals its own success/failure.
  - If you want this script's output to be acted on, pipe it to another
    script that consumes stdout and decides what to do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

try:  # imported from the package, or run as a file (`python3 claude_cli_get_recent_agent_messages.py`)
    from .transcript_events import (build_recent_agent_text_from_relevant_events, find_events_since_last_user_prompt, parse_event_lines)
except ImportError:
    from transcript_events import (build_recent_agent_text_from_relevant_events, find_events_since_last_user_prompt, parse_event_lines)  # type: ignore[no-redef]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract assistant replies since the last user message from a Claude Code transcript.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit raw JSON events (NDJSON) instead of stripped text.",
    )
    parser.add_argument(
        "--include-tool-calls",
        action="store_true",
        help="In text mode, also emit a one-line summary for each tool_use block (the CALL).",
    )
    parser.add_argument(
        "--tool-results",
        action="store_true",
        dest="tool_results",
        help="In text mode, also include tool_result OUTPUT blocks (the result "
             "returned to the assistant), summarized as '[tool_result] <text>'. "
             "Distinct from --include-tool-calls, which summarizes the call.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        dest="max_chars",
        help="If set, emit only the LAST N characters of the text output (the "
             "'most recent, from the bottom' capture window). Intentionally has "
             "NO default: the caller supplies the value from settings so the "
             "window size is never hard-coded in this portable script.",
    )
    parser.add_argument(
        "--transcript-path",
        type=str,
        default=None,
        help="Override transcript path (bypass stdin). For testing.",
    )
    parser.add_argument(
        "--separator",
        type=str,
        default="\n\n",
        help="Separator between assistant messages in text mode. Default: blank line.",
    )
    return parser.parse_args()


def read_hook_payload() -> dict:
    """Read the JSON payload from stdin (Claude Code hook input)."""
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: stdin payload is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)


def resolve_transcript_path(args: argparse.Namespace) -> Path:
    """Either use the CLI override or read from the hook payload."""
    if args.transcript_path:
        path = Path(args.transcript_path)
    else:
        payload = read_hook_payload()
        if "transcript_path" not in payload:
            print(
                "ERROR: hook payload missing 'transcript_path' field. "
                "Are you sure this script was invoked from a Stop hook?",
                file=sys.stderr,
            )
            sys.exit(2)
        path = Path(payload["transcript_path"])

    if not path.exists():
        print(f"ERROR: transcript not found at {path}", file=sys.stderr)
        sys.exit(1)
    return path


def parse_events(path: Path) -> Iterator[dict]:
    """Yield parsed events from a JSONL file. Tolerates malformed lines."""
    with path.open() as f:
        yield from parse_event_lines(f)


def emit_text(
    relevant_events: list[dict],
    include_tool_calls: bool,
    include_tool_results: bool,
    separator: str,
    max_chars: "int | None",
) -> None:
    """Print the assembled capture string to stdout (CLI path)."""
    output_text = build_recent_agent_text_from_relevant_events(
        relevant_events, include_tool_calls, include_tool_results, separator, max_chars
    )
    if not output_text:
        return
    sys.stdout.write(output_text)
    if not output_text.endswith("\n"):
        sys.stdout.write("\n")


def emit_json(assistant_events: list[dict]) -> None:
    """Print raw JSON events as NDJSON, one per line."""
    for event in assistant_events:
        sys.stdout.write(json.dumps(event, separators=(",", ":")))
        sys.stdout.write("\n")


def main() -> int:
    args = parse_args()
    transcript_path = resolve_transcript_path(args)

    events = list(parse_events(transcript_path))
    relevant_events = find_events_since_last_user_prompt(events)

    if args.json:
        assistant_events = [
            event for event in relevant_events if event.get("type") == "assistant"
        ]
        emit_json(assistant_events)
    else:
        emit_text(
            relevant_events,
            args.include_tool_calls,
            args.tool_results,
            args.separator,
            args.max_chars,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
