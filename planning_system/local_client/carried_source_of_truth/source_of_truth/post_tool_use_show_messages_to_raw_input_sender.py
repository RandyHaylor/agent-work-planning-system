"""PostToolUse hook script: drains pending-user-messages targeted at THIS session's project.

Hook contract:
  stdin = JSON containing at least {"session_id": "..."} per Claude Code's hook spec.
  stdout = JSON object; if non-empty, must include "systemMessage" (user-only text).

Gating logic (this is a GLOBAL hook, so it must self-gate):
  1. Read current session_id from stdin JSON.
  2. Resolve it to a SoT project_id via project_identifier_resolver.
  3. If unregistered -> emit {} and exit (do not touch the queue).
  4. Otherwise drain ONLY messages targeted at that project_id and emit them.

Non-SoT sessions, broken installs, or queue-empty cases all emit {} -- so this
hook is safe and effectively zero-cost to register globally.
"""
from __future__ import annotations

import json
import sys


def _main() -> int:
    try:
        raw_stdin_text = sys.stdin.read()
    except Exception:
        print(json.dumps({}))
        return 0
    try:
        hook_input = json.loads(raw_stdin_text) if raw_stdin_text else {}
    except json.JSONDecodeError:
        hook_input = {}
    current_session_id = (
        hook_input.get("session_id")
        or hook_input.get("sessionId")
    )
    if not current_session_id:
        print(json.dumps({}))
        return 0

    try:
        from .project_identifier_resolver import resolve_project_id_for_session
        from .pending_messages_for_raw_input_sender import show_pending_messages_to_raw_input_sender_for_project
    except Exception:
        print(json.dumps({}))
        return 0

    matched_project_id = resolve_project_id_for_session(current_session_id)
    if matched_project_id is None:
        print(json.dumps({}))
        return 0

    drained = show_pending_messages_to_raw_input_sender_for_project(matched_project_id)
    if not drained:
        print(json.dumps({}))
        return 0

    combined_system_message_text = "\n".join(
        f"[{m.get('source_label', 'sot')}] {m.get('message_text', '')}"
        for m in drained
    )
    print(json.dumps({"systemMessage": combined_system_message_text}))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
