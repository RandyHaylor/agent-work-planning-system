"""Client halt (build log #68): `planning halt` kills every process this client started (task sessions, review
loops, reviewer processes), each by its whole process group, without waiting; nothing new starts until `planning
resume`. A second SIGINT/SIGTERM aborts the review in progress. Real subprocesses, no model calls."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from planning_system.api_client import ClientSettings
from planning_system.api_client.fakes import FakePlanningApiClient
from planning_system.contract import Halted
from planning_system.local_client import LocalClient
from planning_system.local_client.client_paths import ClientPaths
from planning_system.local_client.halt import (ALREADY_GONE, KILLED, TERMINATED, ClientHalted, ClientSessionTracker,
                                               HaltMarker, ProcessKiller, SessionHalter, client_session_control,
                                               live_members)
from planning_system.local_client.harness_adapters.claude_code.ai_cli_adapter_claude_code import \
    ClaudeCodeReviewerSessionHandleViaResume
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_mode import ReviewModeLoop
from planning_system.local_client.review_mode.reviewer_backends.conversations import ReviewWorkerConversation
from planning_system.local_client.review_mode.reviewer_backends.fakes import FakeReviewerBackend, verdict_json
from planning_system.local_client.review_mode.serve_until_signalled import run_review_mode
from planning_system.local_client.review_worker.fakes import FakeReviewWorker
from planning_system.local_client.task_runner import (SESSION_REVIEW_LOOP, SESSION_REVIEWER, SESSION_TASK,
                                                      RunningSession, RunningSessionsRegistry, TaskRunner,
                                                      TaskSessionLauncher, TaskStartRequest)

pytestmark = pytest.mark.skipif(not hasattr(os, "killpg") or not Path("/proc/self/stat").exists(),
                                reason="process groups + /proc (Linux)")

# a "session" that starts a grandchild, like claude starting tools: the whole group must go
SESSION_WITH_CHILD = ("import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; "
                      "time.sleep(120)']); time.sleep(120)")
IGNORES_SIGTERM = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)"


@pytest.fixture
def paths(tmp_path):
    return ClientPaths(tmp_path / "client-home")


@pytest.fixture
def control(paths):
    return client_session_control(paths)


def _spawn(code: str, new_group: bool = True) -> subprocess.Popen:
    process = subprocess.Popen([sys.executable, "-c", code], start_new_session=new_group)
    time.sleep(0.3)                                   # let it start its grandchild
    return process


def _gone(process_group: int, within: float = 5.0) -> bool:
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if not list(live_members(process_group)):
            return True
        time.sleep(0.05)
    return False


# --------------------------------------------------------------------------- marker + registry

def test_marker_set_clear_and_refusal(tmp_path):
    marker = HaltMarker(tmp_path / "HALTED")
    marker.ensure_not_halted()
    marker.set()
    assert marker.is_set()
    with pytest.raises(ClientHalted, match="planning resume"):
        marker.ensure_not_halted()
    assert isinstance(ClientHalted(), Halted)
    assert marker.clear() is True and marker.clear() is False
    marker.ensure_not_halted()


def test_registry_keeps_kind_and_forgets(tmp_path):
    registry = RunningSessionsRegistry(tmp_path / "running.json")
    registry.record(RunningSession("review_loop-9", 4, "reviewer", "/w", 9, kind=SESSION_REVIEW_LOOP,
                                   process_group=False))
    registry.record(RunningSession("worker-1", 5, "worker", "/w", 10))
    assert {(s.agent_id, s.kind, s.process_group) for s in registry.all()} == {
        ("review_loop-9", SESSION_REVIEW_LOOP, False), ("worker-1", SESSION_TASK, True)}
    registry.forget("review_loop-9")
    registry.forget("never-there")
    assert [s.agent_id for s in registry.all()] == ["worker-1"]


def test_old_registry_rows_without_kind_load_as_tasks(tmp_path):
    file = tmp_path / "running.json"
    file.write_text(json.dumps({"w": {"agent_id": "w", "node_id": 1, "role": "worker", "working_directory": "/",
                                      "pid": None, "alive": True}}))
    assert RunningSessionsRegistry(file).all()[0].kind == SESSION_TASK


# --------------------------------------------------------------------------- halt kills real process groups

def test_halt_kills_every_registered_process_group_and_reports(control, paths):
    tracker, halter = control
    task = _spawn(SESSION_WITH_CHILD)
    reviewer = _spawn(SESSION_WITH_CHILD)
    loop = _spawn("import time; time.sleep(120)", new_group=False)      # a review loop: killed by pid alone
    registry = RunningSessionsRegistry(paths.running_sessions_file)
    registry.record(RunningSession("worker-1", 7, "worker", "/w", task.pid))
    tracker.launched(reviewer.pid, "reviewer r-1")
    registry.record(RunningSession(f"review_loop-{loop.pid}", 3, "reviewer", "/w", loop.pid,
                                   kind=SESSION_REVIEW_LOOP, process_group=False))
    assert len(list(live_members(task.pid))) == 2                         # session + its grandchild

    started = time.monotonic()
    report = halter.halt()
    for process in (task, reviewer, loop):
        process.wait(timeout=5)                                           # reap our direct children
    assert time.monotonic() - started < 5
    assert report["halted"] is True
    assert [(row["kind"], row["outcome"]) for row in report["killed"]] == [
        (SESSION_REVIEW_LOOP, TERMINATED), (SESSION_REVIEWER, TERMINATED), (SESSION_TASK, TERMINATED)]
    assert _gone(task.pid) and _gone(reviewer.pid)                        # grandchildren too
    rows = {s.agent_id: s for s in registry.all()}
    assert rows["worker-1"].alive is False and set(rows) == {"worker-1"}  # loops/reviewers forgotten
    assert HaltMarker(paths.halt_marker_file).is_set()


def test_a_process_ignoring_sigterm_is_killed_after_the_grace(tmp_path):
    stubborn = _spawn(IGNORES_SIGTERM)
    outcomes = ProcessKiller(grace_seconds=0.5).kill_all([
        type("T", (), {"pid": stubborn.pid, "process_group": True})()])
    stubborn.wait(timeout=5)
    assert outcomes == [KILLED]
    assert ProcessKiller(0.1).kill_all([type("T", (), {"pid": stubborn.pid, "process_group": True})()]) == [
        ALREADY_GONE]


def test_nothing_new_starts_while_halted_until_resume(control, paths, api, settings, task_node):
    tracker, halter = control
    halter.halt()
    adapter = FakeAiCliAdapter()
    runner = TaskRunner(TaskSessionLauncher(api, adapter, settings),
                        RunningSessionsRegistry(paths.running_sessions_file), tracker.ensure_not_halted)
    request = TaskStartRequest(task_node["id"], "worker-2", "worker", "tok", Path("/tmp"))
    with pytest.raises(ClientHalted):
        runner.start_task(request)
    with pytest.raises(ClientHalted):
        tracker.before_launch()
    with pytest.raises(ClientHalted):
        with tracker.review_loop(1):
            pass
    assert adapter.sessions == []
    assert halter.resume() == {"resumed": True, "was_halted": True}
    runner.start_task(request)
    assert len(adapter.sessions) == 1


def test_reviewer_turn_is_refused_before_any_process_starts_and_is_tracked_otherwise(control, paths):
    tracker, halter = control
    handle = ClaudeCodeReviewerSessionHandleViaResume("r-1", [], [], True, "haiku", process_tracker=tracker)
    seen = {}

    class FakePopen:
        pid = 424242

        def __init__(self, command, **kwargs):
            seen["kwargs"] = kwargs
            seen["registered"] = [s.agent_id for s in RunningSessionsRegistry(paths.running_sessions_file).all()]
            self.stdin = type("In", (), {"write": lambda *a: None, "close": lambda *a: None})()
            import io
            self.stdout = io.StringIO(json.dumps({"type": "result", "result": "ok"}) + "\n")
            self.stderr = io.StringIO("")

        def poll(self):
            return 0

        def kill(self):
            pass

    target = "planning_system.local_client.harness_adapters.claude_code.ai_cli_adapter_claude_code.subprocess.Popen"
    with patch(target, FakePopen):
        assert handle.send_prompt_and_await_response("hi") == "ok"
        assert seen["kwargs"]["start_new_session"] is True
        assert RunningSessionsRegistry(paths.running_sessions_file).all() == []     # forgotten after the turn
        halter.halt()
        seen.clear()
        with pytest.raises(ClientHalted):
            handle.send_prompt_and_await_response("again")
        assert seen == {}                                                            # no process launched


def test_reviewer_conversation_does_not_turn_a_halt_into_a_retry():
    class HaltedWorker(FakeReviewWorker):
        def ask(self, question, context_paths=()):
            raise ClientHalted()

    with pytest.raises(ClientHalted):
        ReviewWorkerConversation(HaltedWorker(FakeAiCliAdapter())).say("turn")


# --------------------------------------------------------------------------- review loop

@pytest.fixture
def review_task(server):
    project = server.seed_project("Proj")
    node = server._new_node(project["id"], "Task", "task", "do it", [], None)
    return project["id"], node["id"], server.issue_token("worker", project["id"], node["id"], "reviewer-1")


@pytest.fixture
def reviewer_api(server, review_task):
    return FakePlanningApiClient(ClientSettings("https://127.0.0.1:8443", None, review_task[2]),
                                 transport=server.transport())


def test_halted_loop_takes_nothing_and_stops(control, server, reviewer_api, review_task):
    tracker, halter = control
    server.seed_review(review_task[0], review_task[1])
    halter.halt()
    backend = FakeReviewerBackend([verdict_json(True)])
    ReviewModeLoop(reviewer_api, backend, review_task[0], 0.01, tracker.ensure_not_halted).serve(threading.Event())
    assert backend.prompts == [] and not any(r.path == "/reviews/take" for r in server.requests)


def test_loop_registers_itself_while_serving(control, paths, server, reviewer_api, review_task):
    tracker, _ = control
    seen = []

    class Probe:
        def run_once(self):
            seen.append([(s.kind, s.pid, s.process_group) for s in RunningSessionsRegistry(
                paths.running_sessions_file).all()])

    run_review_mode(Probe(), True, review_task[0], tracker)
    assert seen == [[(SESSION_REVIEW_LOOP, os.getpid(), False)]]
    assert RunningSessionsRegistry(paths.running_sessions_file).all() == []


class _SignalSelfLoop:
    """serve() sends this process SIGTERM `signals` times mid-review, then 'submits' unless interrupted."""

    def __init__(self, signals: int):
        self.signals = signals
        self.submitted = False
        self.turns = 0

    def run_once(self):
        return None

    def serve(self, stop):
        for _ in range(self.signals):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)                       # the handler runs here
            self.turns += 1
        self.submitted = True                     # finishing the review in hand


def test_first_signal_finishes_the_review_second_aborts_it():
    graceful = _SignalSelfLoop(1)
    assert run_review_mode(graceful, False) == {"stopped": True}
    assert graceful.submitted

    aborted = _SignalSelfLoop(2)
    assert run_review_mode(aborted, False) == {"stopped": True, "aborted": True}
    assert aborted.turns == 1 and not aborted.submitted                   # no more turns, nothing submitted
    assert signal.getsignal(signal.SIGTERM) is not None                   # handlers restored


def test_when_halted_the_first_signal_aborts(control, paths):
    tracker, _ = control

    class HaltThenSignal(_SignalSelfLoop):
        def serve(self, stop):
            HaltMarker(paths.halt_marker_file).set()      # what `planning halt` does before it signals the loop
            super().serve(stop)

    loop = HaltThenSignal(1)
    assert run_review_mode(loop, False, 1, tracker)["aborted"] is True
    assert not loop.submitted


def test_end_to_end_task_session_started_by_the_real_runner_is_gone_after_halt(tmp_path, monkeypatch, paths, api,
                                                                              settings, task_node):
    """Real TaskRunner + real Claude Code adapter, with a fake `claude` on PATH that starts a grandchild."""
    from planning_system.local_client.harness_adapters import AdapterConfig, adapter_for

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_claude = bin_dir / "claude"
    fake_claude.write_text(f"#!{sys.executable}\nimport subprocess, sys, time\nsys.stdin.read()\n"
                           f"subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
                           f"time.sleep(120)\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    tracker, halter = client_session_control(paths)
    adapter = adapter_for(AdapterConfig(), session_logs_directory=paths.session_logs_directory,
                          process_tracker=tracker)
    runner = TaskRunner(TaskSessionLauncher(api, adapter, settings),
                        RunningSessionsRegistry(paths.running_sessions_file), tracker.ensure_not_halted)
    runner.start_task(TaskStartRequest(task_node["id"], "11111111-1111-4111-8111-111111111111", "worker", "tok",
                                       tmp_path))
    pid = runner.running_tasks()[0].pid
    deadline = time.monotonic() + 5
    while len(list(live_members(pid))) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(list(live_members(pid))) == 2
    report = halter.halt()
    assert [(r["kind"], r["pid"]) for r in report["killed"]] == [(SESSION_TASK, pid)]
    assert _gone(pid)
    with pytest.raises(ClientHalted):
        runner.start_task(TaskStartRequest(task_node["id"], "22222222-2222-4222-8222-222222222222", "worker", "tok",
                                           tmp_path))


# --------------------------------------------------------------------------- facade + cli

def test_local_client_halt_and_resume_delegate(control, paths):
    tracker, halter = control
    client = LocalClient(None, None, None, None, None, review_mode_factory=lambda *a: None,
                         session_tracker=tracker, session_halter=halter)
    assert client.halt() == {"halted": True, "killed": []}
    with pytest.raises(ClientHalted):
        client.serve_reviews(1)
    assert client.resume()["was_halted"] is True
