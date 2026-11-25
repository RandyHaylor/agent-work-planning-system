"""Client side of spec test 21 on fakes: `planning review serve --once` -> verdict on the (fake) server ->
`planning review list --status failed` shows it. Plus graceful stop on SIGTERM. Facade on [fake, real]."""
from __future__ import annotations

import io
import json
import os
import signal

import pytest

from planning_system.api_client import ClientSettings
from planning_system.api_client.fakes import FakePlanningApiClient, FakePlanningServer
from planning_system.cli import CliDependencies, PlanningCommandLine
from planning_system.local_client import LocalClient
from planning_system.local_client.fakes import (FakeExchangeCache, FakeHookInstaller, FakeLocalClient)
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_mode import ReviewModeLoop
from planning_system.local_client.review_mode.reviewer_backends.fakes import FakeReviewerBackend, verdict_json
from planning_system.local_client.review_worker.fakes import FakeReviewWorker
from planning_system.local_client.task_runner.fakes import FakeTaskRunner


@pytest.fixture(params=[pytest.param(FakeLocalClient, id="fake"), pytest.param(LocalClient, id="real")])
def facade_class(request):
    return request.param


class Setup:
    def __init__(self, facade_class, replies):
        self.server = FakePlanningServer()
        project = self.server.seed_project("Proj")
        review_task = self.server._new_node(project["id"], "citation review", "task", "reviews", ["review"], None)
        self.project_id = project["id"]
        self.record = self.server.seed_review(project["id"], review_task["id"])
        self.worker_token = self.server.issue_token("worker", project["id"], review_task["id"], "reviewer-1")
        self.planner_token = self.server.issue_token("planner", project["id"], None, "planner-1")
        self.backend = FakeReviewerBackend(replies)
        self.factory_calls = []

        def api_for(settings):
            return FakePlanningApiClient(settings, transport=self.server.transport())

        def local_for(settings):
            def review_mode(project_id, backend, model, poll_seconds):
                self.factory_calls.append((project_id, backend, model, poll_seconds))
                return ReviewModeLoop(api_for(settings), self.backend, project_id, poll_seconds)
            api = api_for(settings)
            return facade_class(FakeTaskRunner(api, FakeAiCliAdapter(), settings),
                                FakeReviewWorker(FakeAiCliAdapter()), None, FakeExchangeCache(),
                                FakeHookInstaller(), review_mode_factory=review_mode)

        self.command_line = PlanningCommandLine(CliDependencies(
            api_factory=api_for, local_client_factory=local_for, admin_login_factory=lambda api: None,
            settings_from_environment=lambda env: ClientSettings("https://127.0.0.1:8443", None,
                                                                 env.get("PLANNING_TOKEN")),
            launch_guidance_editor=lambda: None))

    def run(self, token, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = self.command_line.run(list(argv), {"PLANNING_TOKEN": token}, out, err)
        assert code == 0, err.getvalue()
        return json.loads(out.getvalue())


def test_21_serve_once_then_planner_sees_failed_review(facade_class):
    setup = Setup(facade_class, [verdict_json(False, "quote does not state it", "vendor placement")])
    result = setup.run(setup.worker_token, "review", "serve", "--project", str(setup.project_id),
                       "--backend", "local_llm", "--once")
    assert result == {"review_id": setup.record["id"]}
    assert setup.factory_calls == [(setup.project_id, "local_llm", None, 5.0)]
    failed = setup.run(setup.planner_token, "review", "list", "--project", str(setup.project_id),
                       "--status", "failed")
    assert [(r["id"], r["reason"], r["suggested_title"]) for r in failed] == [
        (setup.record["id"], "quote does not state it", "vendor placement")]
    shown = setup.run(setup.planner_token, "review", "show", setup.record["id"])
    assert shown["status"] == "failed" and shown["reviewer"] == "reviewer-1"


def test_serve_once_with_empty_queue(facade_class):
    setup = Setup(facade_class, [])
    setup.server.reviews.clear()
    assert setup.run(setup.worker_token, "review", "serve", "--project", str(setup.project_id), "--once") == \
        {"review_id": None}


def test_serve_stops_gracefully_on_sigterm(facade_class):
    """SIGTERM arrives mid-review (as from `planning task stop`): the review in hand is still submitted."""
    setup = Setup(facade_class, [])

    class SignalledBackend(FakeReviewerBackend):
        def _ask(self, prompt):
            os.kill(os.getpid(), signal.SIGTERM)
            return verdict_json(True, "quote states it")

    setup.backend = SignalledBackend()
    previous = signal.getsignal(signal.SIGTERM)
    result = setup.run(setup.worker_token, "review", "serve", "--project", str(setup.project_id),
                       "--poll-seconds", "0.01")
    assert result == {"stopped": True}
    assert setup.server.reviews[setup.record["id"]]["status"] == "passed"
    assert signal.getsignal(signal.SIGTERM) == previous
