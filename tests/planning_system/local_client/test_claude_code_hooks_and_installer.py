"""Claude Code capture hooks (to the local cache) and the hook installer (temp settings.json only)."""
from __future__ import annotations

import io
import json

from planning_system.local_client.harness_adapters.claude_code import (
    post_tool_use_capture_askuserquestion_answers as ask_hook)
from planning_system.local_client.harness_adapters.claude_code import user_prompt_submit_hook
from planning_system.local_client.harness_adapters.claude_code.install import (
    ASKUSERQUESTION_MODULE, USER_PROMPT_SUBMIT_MODULE, ClaudeCodeHookInstaller)
from planning_system.local_client.quote_capture.jsonl_exchange_cache import JsonlExchangeCache


def _transcript(tmp_path):
    events = [
        {"type": "user", "message": {"role": "user", "content": "first question"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Shall I use Postgres?"}]}},
    ]
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def test_user_prompt_submit_writes_verbatim_prompt_and_pre_text_to_local_cache(tmp_path):
    cache = JsonlExchangeCache(tmp_path / "exchanges.jsonl")
    payload = {"session_id": "s1", "prompt": "  yes, Postgres\n", "transcript_path": str(_transcript(tmp_path))}
    output = user_prompt_submit_hook.handle_user_prompt_submit(payload, lambda: cache)
    [exchange] = cache.recent(5)
    assert (exchange.session_id, exchange.kind, exchange.user_message) == ("s1", "prompt", "  yes, Postgres\n")
    assert "Shall I use Postgres?" in exchange.pre_text
    assert exchange.local_id in output["hookSpecificOutput"]["additionalContext"]


def test_user_prompt_submit_never_fails_the_session(tmp_path):
    out = io.StringIO()
    def broken_cache():
        raise RuntimeError("disk gone")
    assert user_prompt_submit_hook.main(io.StringIO('{"prompt": "x"}'), out, broken_cache) == 0
    assert json.loads(out.getvalue()) == {}


def test_askuserquestion_answers_become_local_exchanges(tmp_path):
    cache = JsonlExchangeCache(tmp_path / "exchanges.jsonl")
    payload = {"tool_name": "AskUserQuestion", "session_id": "s1",
               "tool_input": {"questions": [{"question": "Which database?"}, {"question": "Which host?"}],
                              "answers": {"Which host?": "Local", "Which database?": "Postgres"}}}
    ask_hook.handle_post_tool_use(payload, cache)
    assert [(e.kind, e.pre_text, e.user_message) for e in cache.recent(5)] == [
        ("question_answer", "Which database?", "Postgres"), ("question_answer", "Which host?", "Local")]


def test_askuserquestion_ignores_other_tools_and_dismissed_dialogs(tmp_path):
    cache = JsonlExchangeCache(tmp_path / "exchanges.jsonl")
    assert ask_hook.handle_post_tool_use({"tool_name": "Bash", "session_id": "s1"}, cache) == {}
    assert ask_hook.handle_post_tool_use({"tool_name": "AskUserQuestion", "session_id": "s1",
                                          "tool_input": {"answers": {}}}, cache) == {}
    assert cache.recent(5) == []


def test_installer_registers_both_hooks_once_and_keeps_existing_entries(tmp_path):
    settings_path = tmp_path / "settings.json"
    other = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}
    settings_path.write_text(json.dumps({"model": "opus", "hooks": {"PostToolUse": [other]}}))
    installer = ClaudeCodeHookInstaller(settings_path, python_executable="/usr/bin/python3")
    assert installer.ensure_hook_entries() is True
    assert installer.ensure_hook_entries() is False          # idempotent
    data = json.loads(settings_path.read_text())
    assert data["model"] == "opus" and other in data["hooks"]["PostToolUse"]
    commands = [h["command"] for entries in data["hooks"].values() for e in entries for h in e["hooks"]]
    assert commands.count(installer.command_for(USER_PROMPT_SUBMIT_MODULE)) == 1
    assert commands.count(installer.command_for(ASKUSERQUESTION_MODULE)) == 1
    assert list(tmp_path.glob("settings.json.bak.*"))


def test_installer_replaces_entries_from_another_interpreter(tmp_path):
    settings_path = tmp_path / "settings.json"
    ClaudeCodeHookInstaller(settings_path, python_executable="/old/python").install()
    ClaudeCodeHookInstaller(settings_path, python_executable="/new/python").install()
    text = settings_path.read_text()
    assert "/old/python" not in text and text.count("/new/python") == 2
