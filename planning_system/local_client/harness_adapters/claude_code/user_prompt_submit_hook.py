"""UserPromptSubmit hook for Claude Code: writes the verbatim prompt + pre-text (preceding agent output,
via claude_cli_get_recent_agent_messages) to quote_capture's local cache. Nothing is sent to the server.

In SoT this handler lived inside cli_entrypoint.py (see carried_source_of_truth/source_of_truth/cli_entrypoint.py,
the user-prompt-submit verb). Level 6 scaffold: hollow; level 7 ports that handler here.
"""
from __future__ import annotations


def handle_user_prompt_submit(hook_payload: dict) -> dict:
    """Claude Code hook stdin JSON -> hook stdout JSON."""
    raise NotImplementedError("level 7")


def main() -> int:
    raise NotImplementedError("level 7")
