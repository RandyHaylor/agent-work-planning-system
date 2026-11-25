from __future__ import annotations

import json
from pathlib import Path

from source_of_truth.project_identifier_resolver import resolve_project_id_for_session


def _write_project_settings_with_member_session(
    projects_parent_dir: Path, project_id: str, session_ids: list[str]
) -> None:
    project_dir = projects_parent_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project-settings.json").write_text(json.dumps({
        "member_sessions": [{"session_id": sid, "conversation_path": "/x"} for sid in session_ids],
    }))


def test_returns_matching_project_id(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    projects_parent_dir = tmp_path / ".source-of-truth" / "projects"
    _write_project_settings_with_member_session(projects_parent_dir, "alpha", ["sess-1"])
    _write_project_settings_with_member_session(projects_parent_dir, "beta", ["sess-2", "sess-3"])
    assert resolve_project_id_for_session("sess-3") == "beta"
    assert resolve_project_id_for_session("sess-1") == "alpha"


def test_returns_none_when_no_match(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".source-of-truth" / "projects").mkdir(parents=True, exist_ok=True)
    assert resolve_project_id_for_session("sess-not-there") is None
