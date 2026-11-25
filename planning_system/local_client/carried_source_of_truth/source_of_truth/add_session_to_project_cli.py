"""Standalone CLI: add a session_id (and its conversation path) to a project's membership.

Onus is on the user (or the user's AI agent) to call this whenever a session is
spawned/forked/compacted/transitioned and should be considered part of an existing
source-of-truth project.

Usage:
    python add_session_to_project_cli.py <project_id> <session_id> <conversation_path>
"""
from __future__ import annotations

import sys

from .load_config import (
    PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY,
    PROJECT_SETTINGS_OVERRIDE_COMMENT_TEXT,
    ensure_root_directories_exist,
    load_project_settings,
    project_settings_file_path,
    save_project_settings,
)
from .project_identifier_resolver import resolve_project_id_for_session


class SessionAlreadyInDifferentProjectError(ValueError):
    """A session may belong to only one source-of-truth project at a time."""


def add_session_to_project(project_id: str, session_id: str, conversation_path: str) -> bool:
    """Returns True if a new membership was added, False if the session was already a member.

    A session may belong to only ONE source-of-truth project. Attempting to add it
    to a different project raises SessionAlreadyInDifferentProjectError.
    """
    ensure_root_directories_exist()
    existing_project_id_for_session = resolve_project_id_for_session(session_id)
    if existing_project_id_for_session is not None and existing_project_id_for_session != project_id:
        raise SessionAlreadyInDifferentProjectError(
            f"session_id {session_id!r} is already a member of source-of-truth project "
            f"{existing_project_id_for_session!r}. A session may belong to only one project; "
            f"manually remove it from that project first (delete its entry from "
            f"{project_settings_file_path(existing_project_id_for_session)} -> member_sessions)."
        )
    project_settings_file_already_existed = project_settings_file_path(project_id).exists()
    settings = load_project_settings(project_id)
    if not project_settings_file_already_existed:
        # Fresh project: leave `overrides` empty (inherit all globals) but seed an
        # inline JSON "comment" documenting how to override each global setting.
        settings.raw_extra.setdefault(
            PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY,
            PROJECT_SETTINGS_OVERRIDE_COMMENT_TEXT,
        )
    for existing_member in settings.member_sessions:
        if isinstance(existing_member, dict) and existing_member.get("session_id") == session_id:
            return False
    settings.member_sessions.append({
        "session_id": session_id,
        "conversation_path": conversation_path,
    })
    save_project_settings(settings)
    return True


def _main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: add_session_to_project_cli.py <project_id> <session_id> <conversation_path>",
            file=sys.stderr,
        )
        return 2
    try:
        was_added = add_session_to_project(sys.argv[1], sys.argv[2], sys.argv[3])
    except SessionAlreadyInDifferentProjectError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("added" if was_added else "already_present")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
