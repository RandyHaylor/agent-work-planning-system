"""task_runner contract (05-spec-task-assignment.md tests 6-8; 05-spec-local-client.md tests 1-3), on [fake, real]."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.task_runner import (RunningSessionsRegistry, TaskRunner, TaskSessionLauncher,
                                                      TaskStartRequest)
from planning_system.local_client.task_runner.fakes import FakeTaskRunner

XFAIL_REAL = pytest.mark.xfail(strict=False, reason="level 7")

WORKER_TOKEN = "tok-worker-secret"


def _fake(api, adapter, settings, tmp_path):
    return FakeTaskRunner(api, adapter, settings)


def _real(api, adapter, settings, tmp_path):
    return TaskRunner(TaskSessionLauncher(api, adapter, settings), RunningSessionsRegistry(tmp_path / "sessions.json"))


@pytest.fixture(params=[pytest.param(_fake, id="fake"), pytest.param(_real, id="real", marks=XFAIL_REAL)])
def build_runner(request, api, settings, tmp_path):
    return lambda adapter: request.param(api, adapter, settings, tmp_path)


def _request(node, role="worker", agent="worker-1"):
    return TaskStartRequest(node["id"], agent, role, WORKER_TOKEN, Path("/tmp/wt"), ("Bash",))


def _wait_for_prompt(handle):
    deadline = time.monotonic() + 2
    while not handle.prompts and time.monotonic() < deadline:
        time.sleep(0.01)
    return handle.prompts[0]


def test_start_registers_agent_launches_one_session_and_returns_without_waiting(build_runner, server, task_node):
    release = threading.Event()
    adapter = FakeAiCliAdapter(release=release)
    runner = build_runner(adapter)
    session_id = runner.start_task(_request(task_node))   # returns although the session is still blocked
    release.set()
    assert session_id == "worker-1"
    assert [r.path for r in server.requests if r.method == "POST"] == ["/agents"]
    assert len(adapter.sessions) == 1
    assert [(s.agent_id, s.node_id, s.alive) for s in runner.running_tasks()] == [("worker-1", task_node["id"], True)]


def test_token_only_in_environment_and_prompt_has_guidance_and_context(build_runner, task_node):
    adapter = FakeAiCliAdapter()
    build_runner(adapter).start_task(_request(task_node))
    handle = adapter.sessions[0]
    prompt = _wait_for_prompt(handle)
    assert handle.spec.environment["PLANNING_TOKEN"] == WORKER_TOKEN
    assert WORKER_TOKEN not in prompt
    assert "worker guidance" in prompt
    assert "context for Build the thing" in prompt


def test_planner_role_uses_planner_guidance(build_runner, server, task_node):
    adapter = FakeAiCliAdapter()
    build_runner(adapter).start_task(_request(task_node, role="planner", agent="devmgr-1"))
    assert "planner guidance" in _wait_for_prompt(adapter.sessions[0])
    assert any(r.path == "/guidance/planner" for r in server.requests)


def test_stop_terminates_marks_not_alive_and_never_calls_server(build_runner, server, task_node):
    adapter = FakeAiCliAdapter()
    runner = build_runner(adapter)
    runner.start_task(_request(task_node))
    _wait_for_prompt(adapter.sessions[0])
    requests_before = len(server.requests)
    runner.stop_task("worker-1")
    assert not adapter.sessions[0].is_alive()
    assert [s.alive for s in runner.running_tasks()] == [False]
    assert len(server.requests) == requests_before
    assert server.nodes[task_node["id"]]["state"] == "open"
