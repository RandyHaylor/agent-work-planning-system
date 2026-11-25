"""review_worker contract (05-spec-review-dispatch.md tests 1-3), on [fake, real]."""
from __future__ import annotations

from pathlib import Path

import pytest

from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_worker import ReviewWorker
from planning_system.local_client.review_worker.fakes import FakeReviewWorker
from planning_system.local_client.task_runner import TaskStartRequest
from planning_system.local_client.task_runner.fakes import FakeTaskRunner

XFAIL_REAL = pytest.mark.xfail(strict=False, reason="level 7")


@pytest.fixture(params=[pytest.param(FakeReviewWorker, id="fake"),
                        pytest.param(ReviewWorker, id="real", marks=XFAIL_REAL)])
def worker_class(request):
    return request.param


def test_2_ask_returns_answer_and_reuses_session(worker_class, tmp_path):
    adapter = FakeAiCliAdapter(reply=lambda handle, prompt: f"answer {len(handle.prompts)}")
    worker = worker_class(adapter, thinking_log_path=tmp_path / "log.txt")
    first = worker.ask("Is this right?", [Path("/repo/a.py")])
    second = worker.ask("And this?")
    assert first.startswith("answer") and second.startswith("answer")
    assert len(adapter.sessions) == 1
    assert any("Is this right?" in p and "/repo/a.py" in p for p in adapter.sessions[0].prompts)


def test_3_rotates_once_on_context_exhaustion(worker_class, tmp_path):
    def reply(handle, prompt):
        return "Prompt is too long" if handle is adapter.sessions[0] else "fresh answer"
    adapter = FakeAiCliAdapter(reply=reply)
    answer = worker_class(adapter, thinking_log_path=tmp_path / "log.txt").ask("q")
    assert answer == "fresh answer"
    assert len(adapter.sessions) == 2
    assert not adapter.sessions[0].is_alive()


def test_1_review_node_goes_through_the_same_routes_as_any_task(server, api, settings, task_node):
    """A review is an ordinary task labelled `review`: create, assign, start, turn in, done."""
    review = api.create_node(task_node["parent_id"], "Review the thing", "task", "check it", labels=["review"],
                             depends_on=[task_node["id"]])
    assignment = api.assign(review["id"], "reviewer-1", "review/x")
    FakeTaskRunner(api, FakeAiCliAdapter(), settings).start_task(
        TaskStartRequest(review["id"], "reviewer-1", "worker", assignment["worker_token"]))
    api.with_token(assignment["worker_token"]).add_content(review["id"], "looks good", ["verdict"])
    api.set_state(review["id"], "done")
    paths = [(r.method, r.path) for r in server.requests]
    rid = review["id"]
    for expected in [("POST", "/nodes"), ("POST", f"/nodes/{rid}/assign"), ("POST", "/agents"),
                     ("POST", f"/nodes/{rid}/content"), ("POST", f"/nodes/{rid}/state")]:
        assert expected in paths
    assert not any("review" in path for _, path in paths)   # no review-specific route
