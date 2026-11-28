"""Review logging (build log #70). User 2026-11-28: "Ensure there's logging obviously of details from all reviews".
Client: one JSONL record per review attempt, every backend, through a ReviewConversation decorator; server: the
verdict carries backend, model, profile, granularity and prompt version."""
from __future__ import annotations

import json

import pytest

from planning_system.api_client import ClientSettings
from planning_system.api_client.fakes import FakePlanningApiClient
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_mode import (ReviewerBackendFactory, ReviewerProfile, ReviewModeLoop,
                                                      ReviewPacket, ReviewerUnavailable, UnparseableVerdict)
from planning_system.local_client.review_mode.prompt_version import PROMPT_VERSION, prompt_version
from planning_system.local_client.review_mode.review_log import ReviewLogFile
from planning_system.local_client.review_mode.reviewer_backends.fakes import turn_reply
from planning_system.local_client.review_worker import ReviewWorker
from planning_system.model_calls import FakeOneShotModelCall, ModelCallFailed, ModelEndpointFactory

PACKET = ReviewPacket.from_json({
    "review_id": "rev-l", "node_title": "report output", "node_context_summary": "", "claim_tag": "technical",
    "claim_text": "Reports are CSV [ref-1:1-1]. They go to S3. Daily runs.",
    "citations": [{"citation": "[ref-1:1-1]", "origin": "user_exchange", "quoted_text": "Write CSV reports.",
                   "pre_text": "", "full_text": ""}]})
NO = '{"answer": "no", "reason": ""}'
PER_SENTENCE_PASS = ['{"ready": true}', NO, NO, NO, '{"suggested_title": "csv"}']


def bulk(unsupported):
    return json.dumps({"unsupported": [{"sentence": n, "reason": r} for n, r in unsupported],
                       "suggested_title": None})


def factory(model_call=None, adapter=None):
    endpoints = ModelEndpointFactory.__new__(ModelEndpointFactory)
    endpoints.create = lambda name, model=None: model_call
    endpoints.configured_model = lambda name: "gemma-test"
    return ReviewerBackendFactory(
        review_worker_factory=lambda model: ReviewWorker(adapter or FakeAiCliAdapter(
            reply=lambda handle, prompt: turn_reply()), reviewer_model_name=model, allowed_tool_names=[]),
        model_endpoints=endpoints)


@pytest.fixture
def log(tmp_path):
    return ReviewLogFile(tmp_path / "review-log")


def test_every_turn_raw_answer_parsed_answer_timing_and_identity_are_logged(log):
    model_call = FakeOneShotModelCall(list(PER_SENTENCE_PASS))
    backend = factory(model_call).create_from_profile(ReviewerProfile("local", "local_llm", None, "per_sentence"),
                                                      log, project_id=4)
    verdict = backend.review(PACKET)
    [record] = log.recent()
    assert record["review_id"] == "rev-l" and record["kind"] == "content" and record["project_id"] == 4
    assert (record["backend"], record["model"], record["profile"], record["granularity"]) == \
        ("local_llm", "gemma-test", "local", "per_sentence")
    assert record["prompt_version"] == PROMPT_VERSION and len(PROMPT_VERSION) == 12
    assert record["sentences"] == ["Reports are CSV [ref-1:1-1].", "They go to S3.", "Daily runs."]
    [run] = record["runs"]
    assert run["method"] == "per_sentence" and len(run["turns"]) == 5
    assert [t["answer"] for t in run["turns"]] == PER_SENTENCE_PASS
    assert run["turns"][1]["parsed"] == {"answer": "no", "reason": ""}
    assert "Reports are CSV" in run["turns"][0]["sent"]
    assert all(t["seconds"] >= 0 for t in run["turns"])
    assert record["model_calls"] == 5 and record["total_seconds"] >= 0
    assert record["verdict"]["passed"] is True and run["verdict"] == record["verdict"] and verdict.passed
    assert backend.identity.as_dict() == {"backend": "local_llm", "model": "gemma-test", "profile": "local",
                                          "granularity": "per_sentence", "prompt_version": PROMPT_VERSION}


def test_unparseable_answer_is_logged_with_its_raw_text(log):
    backend = factory(FakeOneShotModelCall(["I think it is fine"])).create_from_profile(
        ReviewerProfile("local-bulk", "local_llm", None, "bulk"), log)
    with pytest.raises(UnparseableVerdict):
        backend.review(PACKET)
    [record] = log.recent()
    assert record["runs"][0]["turns"][0]["answer"] == "I think it is fine"
    assert record["runs"][0]["turns"][0]["parsed"] is None
    assert record["error"].startswith("UnparseableVerdict") and record["verdict"] is None


def test_backend_failure_is_logged_on_the_turn(log):
    backend = factory(FakeOneShotModelCall([ModelCallFailed("connection refused")])).create_from_profile(
        ReviewerProfile("local", "local_llm", None, "per_sentence"), log)
    with pytest.raises(ReviewerUnavailable):
        backend.review(PACKET)
    [record] = log.recent()
    assert "connection refused" in record["runs"][0]["turns"][0]["error"]
    assert record["error"].startswith("ReviewerUnavailable") and record["model_calls"] == 1


def test_claude_code_reviews_are_logged_too(log):
    backend = factory().create_from_profile(ReviewerProfile("haiku", "claude_code", "haiku", "bulk"), log)
    backend.review(PACKET)
    [record] = log.recent()
    assert (record["backend"], record["model"], record["granularity"]) == ("claude_code", "haiku", "bulk")
    assert len(record["runs"][0]["turns"]) == 1


def test_compare_mode_logs_both_runs_and_the_disagreement(log):
    model_call = FakeOneShotModelCall(list(PER_SENTENCE_PASS) + [bulk([(2, "S3 not mentioned")])])
    backend = factory(model_call).create_from_profile(ReviewerProfile("local-compare", "local_llm", None, "both"),
                                                      log)
    assert not backend.review(PACKET).passed
    [record] = log.recent()
    assert [run["method"] for run in record["runs"]] == ["per_sentence", "bulk"]
    assert [run["verdict"]["passed"] for run in record["runs"]] == [True, False]
    assert record["compare"] == {"agreed": False, "passed": {"per_sentence": True, "bulk": False}}
    assert record["model_calls"] == 6 and record["granularity"] == "both"
    assert record["verdict"]["reason"].startswith("[per_sentence]")


def test_log_file_recent_filters_and_limits(log):
    for number in range(5):
        log.append({"logged_at": f"2026-11-2{number}T00:00:00+00:00", "review_id": f"rev-{number % 2}"})
    assert [r["review_id"] for r in log.recent(last=2)] == ["rev-1", "rev-0"]
    assert len(log.recent("rev-0", last=20)) == 3
    assert sorted(p.name for p in log._directory.glob("*.jsonl"))[0] == "2026-11-20.jsonl"


def test_prompt_version_changes_with_the_prompt_text(tmp_path):
    from planning_system.local_client.review_mode import prompt_version as module
    from pathlib import Path
    source = Path(module.__file__).parent
    for name in module.PROMPT_FILES:
        (tmp_path / name).write_bytes((source / name).read_bytes())
    assert prompt_version(tmp_path) == PROMPT_VERSION
    (tmp_path / "review_turns.py").write_text("changed")
    assert prompt_version(tmp_path) != PROMPT_VERSION


def test_server_stores_the_reviewer_with_the_verdict_and_show_and_list_return_it():
    from planning_system.contract import Principal
    from planning_system.server import commands as C
    from planning_system.server.commands.command_runner import CommandRunner
    from planning_system.server.commands.fakes import FixedServicesFactory, fake_services
    from planning_system.server.domain.content_review import ReviewedWith
    from planning_system.server.http_api.json_encoding import to_json
    from planning_system.server.storage.fakes import InMemoryStorage

    storage = InMemoryStorage()
    services = fake_services(storage.stores)
    project = services.tree.create(None, "P", "what we're doing", "p")
    record = services.reviews.open_node(project.id, project.id)
    admin = Principal(None, "admin")
    runner = CommandRunner(storage.transactions, storage.stores_for, FixedServicesFactory(services),
                           type("AllowAll", (), {"check": lambda self, *a: None})())
    runner.run(C.TakeReview(project.id), admin)
    with_ = ReviewedWith("claude_code", "haiku", "haiku-compare", "both", PROMPT_VERSION)
    runner.run(C.SubmitReviewVerdict(record.id, False, "[per_sentence] ok; [bulk] no", None, (), with_), admin)
    shown = to_json(runner.run(C.GetReview(record.id), admin))
    assert shown["reviewed_with"] == {"backend": "claude_code", "model": "haiku", "profile": "haiku-compare",
                                      "granularity": "both", "prompt_version": PROMPT_VERSION}
    listed = to_json(runner.run(C.ListReviews(project.id, "failed"), admin))
    assert [r["reviewed_with"]["granularity"] for r in listed] == ["both"]


def test_loop_sends_the_reviewer_identity_with_the_verdict_and_logs_no_token(log, server):
    project = server.seed_project("Proj")
    node = server._new_node(project["id"], "Task", "task", "do it", [], None)
    token = server.issue_token("worker", project["id"], node["id"], "reviewer-1")
    record = server.seed_review(project["id"], node["id"], claim_text="The user wants X [ref-1:1-1].")
    api = FakePlanningApiClient(ClientSettings("https://127.0.0.1:8443", None, token), transport=server.transport())
    backend = factory(FakeOneShotModelCall(['{"ready": true}', NO, NO, '{"suggested_title": null}'])).\
        create_from_profile(ReviewerProfile("local", "local_llm", None, "per_sentence"), log, project["id"])
    ReviewModeLoop(api, backend, project["id"]).run_once()
    assert server.reviews[record["id"]]["reviewed_with"] == backend.identity.as_dict()
    text = "".join(p.read_text() for p in log._directory.glob("*.jsonl"))
    assert token not in text and record["id"] in text
