"""STANDALONE: scan ~/.source-of-truth/projects/*/project-settings.json for a session_id.

Has NO imports from other source_of_truth modules so hooks can invoke it cheaply
and safely without dragging in package state.

Usage as script:
    python project_identifier_resolver.py <session_id>
        prints the matching project_id and exits 0, or exits 1 if no match.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def resolve_project_id_for_session(session_id: str) -> str | None:
    projects_parent_dir = Path.home() / ".source-of-truth" / "projects"
    if not projects_parent_dir.is_dir():
        return None
    for project_subdir in projects_parent_dir.iterdir():
        if not project_subdir.is_dir():
            continue
        settings_file = project_subdir / "project-settings.json"
        if not settings_file.is_file():
            continue
        try:
            settings_data = json.loads(settings_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        member_sessions = settings_data.get("member_sessions", [])
        for member in member_sessions:
            if isinstance(member, dict) and member.get("session_id") == session_id:
                return project_subdir.name
            if isinstance(member, str) and member == session_id:
                return project_subdir.name
    return None


def _main() -> int:
    if len(sys.argv) != 2:
        print("Usage: project_identifier_resolver.py <session_id>", file=sys.stderr)
        return 2
    matched_project_id = resolve_project_id_for_session(sys.argv[1])
    if matched_project_id is None:
        return 1
    print(matched_project_id)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
