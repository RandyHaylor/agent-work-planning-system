"""The what-is-session-id hook must self-gate on project membership like every
other SoT hook: for a session NOT enrolled in a source-of-truth project it emits
{} (never affects unsubscribed sessions), even when the sentinel is present. For
an enrolled session it surfaces the id only when the sentinel is present."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import install

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
SENTINEL = install.WHAT_IS_SESSION_SENTINEL_STRING


def _write_hook_script(tmp_path) -> Path:
    script_path = tmp_path / "what_is_session_id_hook.py"
    script_path.write_text(
        install.WHAT_IS_SESSION_HOOK_TEMPLATE.format(
            sentinel_string=SENTINEL,
            package_dir=REPO_ROOT,
        )
    )
    return script_path


def _register_session_under_home(home_dir: Path, session_id: str) -> None:
    project_dir = home_dir / ".source-of-truth" / "projects" / session_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project-settings.json").write_text(
        json.dumps({"member_sessions": [{"session_id": session_id, "conversation_path": "/x"}]})
    )


def _run_hook(script_path: Path, home_dir: Path, payload: dict) -> str:
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"HOME": str(home_dir), "PATH": os.environ.get("PATH", "")},
    )
    return result.stdout.strip()


def _payload(session_id: str, with_sentinel: bool) -> dict:
    tool_input = {"command": f"cat {SENTINEL}.txt"} if with_sentinel else {"command": "ls"}
    return {"session_id": session_id, "tool_name": "Bash", "tool_input": tool_input}


def test_enrolled_session_with_sentinel_surfaces_id(tmp_path):
    home_dir = tmp_path / "home"
    _register_session_under_home(home_dir, "sess-member")
    script = _write_hook_script(tmp_path)
    out = _run_hook(script, home_dir, _payload("sess-member", with_sentinel=True))
    assert "Current session id: sess-member" in out


def test_unenrolled_session_is_silent_even_with_sentinel(tmp_path):
    home_dir = tmp_path / "home"
    (home_dir / ".source-of-truth" / "projects").mkdir(parents=True, exist_ok=True)
    script = _write_hook_script(tmp_path)
    out = _run_hook(script, home_dir, _payload("sess-not-member", with_sentinel=True))
    assert out == "{}"


def test_enrolled_session_without_sentinel_is_silent(tmp_path):
    home_dir = tmp_path / "home"
    _register_session_under_home(home_dir, "sess-member")
    script = _write_hook_script(tmp_path)
    out = _run_hook(script, home_dir, _payload("sess-member", with_sentinel=False))
    assert out == "{}"
