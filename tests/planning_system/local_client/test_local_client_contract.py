"""LocalClient facade contract (05-spec-local-client.md tests 1-7), on [fake, real], children faked."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest

from planning_system.local_client import LocalClient
from planning_system.local_client.client_credentials.fakes import InMemoryClientCredentials
from planning_system.local_client.fakes import (FakeExchangeCache, FakeHookInstaller, FakeLocalClient,
                                                FakeReferenceSync)
from planning_system.local_client.harness_adapters import HeadlessSessionSpec
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter, SecondFakeAiCliAdapter
from planning_system.local_client.review_worker.fakes import FakeReviewWorker
from planning_system.local_client.task_runner import TaskStartRequest
from planning_system.local_client.task_runner.fakes import FakeTaskRunner

QUOTE_KEY_PLACEHOLDER = "quote-key-placeholder"


@pytest.fixture(params=[pytest.param(FakeLocalClient, id="fake"),
                        pytest.param(LocalClient, id="real")])
def facade_class(request):
    return request.param


@pytest.fixture
def parts(server, api, settings):
    quote_key = server.issue_token("quote_client")
    return {
        "credentials": InMemoryClientCredentials(quote_key=quote_key),
        "cache": FakeExchangeCache({"x1": {"session_id": "s1", "user_message": "build it", "pre_text": "ok?"},
                                    "x2": {"session_id": "s1", "user_message": "yes", "pre_text": "sure?"}}),
        "installer": FakeHookInstaller(),
        "quote_key": quote_key,
    }


def _build(facade_class, api, settings, parts, adapter):
    return facade_class(FakeTaskRunner(api, adapter, settings), FakeReviewWorker(adapter),
                        FakeReferenceSync(api, parts["cache"], parts["credentials"]), parts["cache"],
                        parts["installer"])


def _request(node, role="worker"):
    return TaskStartRequest(node["id"], f"{role}-1", role, "tok-worker", Path("/tmp/wt"))


def test_1_start_task_registers_launches_records_and_returns(facade_class, api, settings, parts, task_node, server):
    adapter = FakeAiCliAdapter()
    client = _build(facade_class, api, settings, parts, adapter)
    assert client.start_task(_request(task_node)) == "worker-1"
    assert ("POST", "/agents") in [(r.method, r.path) for r in server.requests]
    assert adapter.sessions[0].spec.environment["PLANNING_TOKEN"] == "tok-worker"
    assert [s.agent_id for s in client.running_tasks()] == ["worker-1"]


def test_2_stop_task_terminates_without_server(facade_class, api, settings, parts, task_node, server):
    adapter = FakeAiCliAdapter()
    client = _build(facade_class, api, settings, parts, adapter)
    client.start_task(_request(task_node))
    before = len(server.requests)
    client.stop_task("worker-1")
    assert not adapter.sessions[0].is_alive()
    assert [s.alive for s in client.running_tasks()] == [False]
    assert len(server.requests) == before


def test_3_role_selects_guidance(facade_class, api, settings, parts, task_node, server):
    client = _build(facade_class, api, settings, parts, FakeAiCliAdapter())
    client.start_task(_request(task_node, "planner"))
    client.start_task(_request(task_node, "worker"))
    guidance_paths = [r.path for r in server.requests if r.path.startswith("/guidance/")]
    assert guidance_paths == ["/guidance/planner", "/guidance/worker"]


def test_4_ask_reviewer_reuses_then_rotates(facade_class, api, settings, parts):
    answers = iter(["first", "second", "prompt is too long", "after rotation"])
    adapter = FakeAiCliAdapter(reply=lambda handle, prompt: next(answers))
    client = _build(facade_class, api, settings, parts, adapter)
    assert client.ask_reviewer("q1") == "first"
    assert client.ask_reviewer("q2") == "second"
    assert len(adapter.sessions) == 1
    assert client.ask_reviewer("q3") == "after rotation"
    assert len(adapter.sessions) == 2


def test_5_quote_key_only_read_by_reference_sync(facade_class, api, settings, parts, task_node, server):
    adapter = FakeAiCliAdapter()
    client = _build(facade_class, api, settings, parts, adapter)
    client.start_task(_request(task_node))
    session = adapter.sessions[0]
    assert parts["credentials"].reads == 0
    assert parts["quote_key"] not in session.spec.environment.values()
    reference_id = client.cite_exchange("x1")
    assert parts["credentials"].reads == 1
    exchange_posts = [r for r in server.requests if r.path == "/references/user-exchange"]
    assert len(exchange_posts) == 1
    assert exchange_posts[0].headers["authorization"] == f"Bearer {parts['quote_key']}"
    assert exchange_posts[0].body["user_message"] == "build it"
    assert client.cite_exchange("x1") == reference_id      # same content = same reference


def test_5b_hooks_and_exchanges_delegate(facade_class, api, settings, parts):
    client = _build(facade_class, api, settings, parts, FakeAiCliAdapter())
    client.install_hooks()
    assert parts["installer"].installs == 1
    assert [e["local_id"] for e in client.list_exchanges(1)] == ["x2"]


def test_6_second_adapter_swaps_in_unchanged(facade_class, api, settings, parts, task_node):
    adapter = SecondFakeAiCliAdapter(reply=lambda handle, prompt: "codex says hi")
    client = _build(facade_class, api, settings, parts, adapter)
    client.start_task(_request(task_node))
    assert client.ask_reviewer("q") == "codex says hi"
    assert len(adapter.sessions) == 2


@pytest.mark.skipif(not (os.environ.get("PLANNING_RUN_CLAUDE") and shutil.which("claude")),
                    reason="slow, optional: set PLANNING_RUN_CLAUDE=1 with claude on PATH")
def test_7_real_claude_code_headless_session_resumes(tmp_path):
    from planning_system.local_client.harness_adapters.claude_code import ClaudeCodeAdapter
    handle = ClaudeCodeAdapter().spawn_headless_session(
        HeadlessSessionSpec(str(uuid.uuid4()), tmp_path, dict(os.environ), model="haiku"))
    assert handle.send_prompt_and_await_response("Reply with the word ONE.").strip()
    assert handle.send_prompt_and_await_response("Reply with the word TWO.").strip()
    handle.terminate()
