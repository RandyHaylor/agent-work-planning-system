"""Real local pieces end to end: headless handle (fake `claude` on PATH), registry across processes,
quote key file -> reference sync against the fake server, and build_local_client wiring."""
from __future__ import annotations

import os
import stat
import sys
import textwrap
import time
from pathlib import Path

import pytest

from planning_system.api_client.fakes import FakePlanningApiClient
from planning_system.contract import Forbidden
from planning_system.local_client import LocalClient, build_local_client
from planning_system.local_client.client_credentials import FileClientCredentials
from planning_system.local_client.harness_adapters import HeadlessSessionSpec
from planning_system.local_client.harness_adapters.claude_code import ClaudeCodeAdapter
from planning_system.local_client.quote_capture.exchange_capture import ExchangeCaptureService
from planning_system.local_client.quote_capture.fakes import FixedClock, ScriptedAdapter
from planning_system.local_client.quote_capture.jsonl_exchange_cache import JsonlExchangeCache
from planning_system.local_client.quote_capture.production_ports import ApiServerReferences, StoredQuoteKey
from planning_system.local_client.quote_capture.reference_sync import ReferenceSyncService
from planning_system.local_client.task_runner import (RunningSessionsRegistry, TaskRunner, TaskSessionLauncher,
                                                      TaskStartRequest)

posix_only = pytest.mark.skipif(os.name != "posix", reason="fake claude is a POSIX script")

FAKE_CLAUDE = textwrap.dedent(f"""\
    #!{sys.executable}
    import json, os, sys, time
    prompt = sys.stdin.read()
    with open(os.environ["FAKE_CLAUDE_RECORD"], "a") as record:
        record.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(),
                                  "token": os.environ.get("PLANNING_TOKEN"), "prompt": prompt}}) + "\\n")
    time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "0")))
    print(json.dumps({{"type": "result", "result": "echo: " + prompt.strip()[:20]}}), flush=True)
""")


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    record = tmp_path / "record.jsonl"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    return record


@posix_only
def test_headless_session_uses_session_id_then_resume_in_working_dir_with_env(fake_claude, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    handle = ClaudeCodeAdapter(session_logs_directory=tmp_path / "logs").spawn_headless_session(
        HeadlessSessionSpec("sess-1", work, {"PLANNING_TOKEN": "tok-w"}))
    assert handle.send_prompt_and_await_response("hello one") == "echo: hello one"
    assert handle.send_prompt_and_await_response("hello two") == "echo: hello two"
    import json
    first, second = [json.loads(line) for line in fake_claude.read_text().splitlines()]
    assert "--session-id" in first["argv"] and "--resume" in second["argv"]
    assert first["cwd"] == str(work) and first["token"] == "tok-w"
    assert "hello one" not in first["argv"]          # prompt goes on stdin


@posix_only
def test_start_returns_while_session_runs_and_stop_works_from_a_new_runner(fake_claude, tmp_path, monkeypatch,
                                                                           server, api, settings, task_node):
    monkeypatch.setenv("FAKE_CLAUDE_SLEEP", "30")
    adapter = ClaudeCodeAdapter(session_logs_directory=tmp_path / "logs")
    registry_file = tmp_path / "sessions.json"
    runner = TaskRunner(TaskSessionLauncher(api, adapter, settings), RunningSessionsRegistry(registry_file))
    started = time.monotonic()
    runner.start_task(TaskStartRequest(task_node["id"], "worker-1", "worker", "tok-w", tmp_path))
    assert time.monotonic() - started < 10
    [session] = RunningSessionsRegistry(registry_file).all()
    assert session.pid and session.alive
    os.kill(session.pid, 0)                           # still running

    later = TaskRunner(TaskSessionLauncher(api, adapter, settings), RunningSessionsRegistry(registry_file))
    later.stop_task("worker-1")                       # a later `planning task stop`: kills by recorded pid
    assert [s.alive for s in later.running_tasks()] == [False]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.waitpid(session.pid, os.WNOHANG)
            os.kill(session.pid, 0)
        except (ChildProcessError, ProcessLookupError):
            break
        time.sleep(0.05)
    else:
        pytest.fail("session process still running after stop")


def test_reference_sync_reads_quote_key_file_and_posts_with_it(tmp_path, server, settings):
    api = FakePlanningApiClient(settings, transport=server.transport())
    credentials = FileClientCredentials(tmp_path)
    cache = JsonlExchangeCache(tmp_path / "exchanges.jsonl")
    sync = ReferenceSyncService(cache, ApiServerReferences(api), StoredQuoteKey(credentials))
    local_id = ExchangeCaptureService(ScriptedAdapter(), cache, FixedClock()).capture_prompt("s1", "build it")
    with pytest.raises(Forbidden):
        sync.sync(local_id)                           # no quote key stored yet
    quote_key = server.issue_token("quote_client")
    credentials.write_quote_key(quote_key)
    reference_id = sync.sync(local_id)
    post = server.requests[-1]
    assert (post.path, post.headers["authorization"]) == ("/references/user-exchange", f"Bearer {quote_key}")
    assert sync.sync(local_id) == reference_id


def test_build_local_client_wires_real_children_under_client_home(tmp_path, monkeypatch, settings):
    monkeypatch.setenv("PLANNING_CLIENT_HOME", str(tmp_path / "home"))
    client = build_local_client(settings)
    assert isinstance(client, LocalClient)
    assert client.running_tasks() == [] and client.list_exchanges(5) == []
