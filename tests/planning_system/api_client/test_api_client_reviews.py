"""api_client review methods (05-spec-citation-enforcement-and-review.md "Routes"), on [fake, real]."""
from __future__ import annotations

import pytest

from planning_system.api_client import ApiError, ClientSettings, PlanningApiClient
from planning_system.api_client.fakes import FakePlanningApiClient, FakePlanningServer

BASE_URL = "https://127.0.0.1:8443"


@pytest.fixture(params=[pytest.param(FakePlanningApiClient, id="fake"), pytest.param(PlanningApiClient, id="real")])
def client_class(request):
    return request.param


@pytest.fixture
def server():
    return FakePlanningServer()


@pytest.fixture
def ids(server):
    project = server.seed_project()
    node = server._new_node(project["id"], "Task", "task", "do it", [], None)
    return project["id"], node["id"]


@pytest.fixture
def reviewer(client_class, server, ids):
    token = server.issue_token("worker", ids[0], ids[1], "reviewer-1")
    return client_class(ClientSettings(BASE_URL, None, token), transport=server.transport())


def test_routes_and_bodies(reviewer, server, ids):
    project_id, node_id = ids
    record = server.seed_review(project_id, node_id)
    reviewer.list_reviews(project_id, status="pending", node_id=node_id)
    assert (server.requests[-1].method, server.requests[-1].path) == ("GET", "/reviews")
    assert server.requests[-1].params == {"project_id": str(project_id), "status": "pending",
                                          "node_id": str(node_id)}
    packet = reviewer.take_review(project_id)
    assert (server.requests[-1].method, server.requests[-1].path, server.requests[-1].body) == \
        ("POST", "/reviews/take", {"project_id": project_id})
    assert packet["review_id"] == record["id"] and packet["citations"][0]["quoted_text"] == "I want X."
    decided = reviewer.submit_review_verdict(record["id"], False, "slice does not say X", "x choice")
    assert (server.requests[-1].path, server.requests[-1].body) == (
        f"/reviews/{record['id']}/verdict",
        {"passed": False, "reason": "slice does not say X", "suggested_title": "x choice"})
    assert decided["status"] == "failed"
    assert reviewer.get_review(record["id"])["suggested_title"] == "x choice"
    assert server.requests[-1].path == f"/reviews/{record['id']}"


def test_take_empty_queue_returns_none(reviewer, ids):
    assert reviewer.take_review(ids[0]) is None


def test_release_puts_back_to_pending(reviewer, server, ids):
    record = server.seed_review(*ids)
    reviewer.take_review(ids[0])
    reviewer.release_review(record["id"])
    assert (server.requests[-1].method, server.requests[-1].path) == ("POST", f"/reviews/{record['id']}/release")
    assert [r["id"] for r in reviewer.list_reviews(ids[0], status="pending")] == [record["id"]]


def test_verdict_by_non_holder_is_409(reviewer, server, ids):
    record = server.seed_review(*ids)
    with pytest.raises(ApiError) as error:
        reviewer.submit_review_verdict(record["id"], True, "ok")
    assert error.value.status == 409
