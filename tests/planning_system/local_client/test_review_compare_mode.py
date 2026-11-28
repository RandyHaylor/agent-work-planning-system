"""Compare mode, granularity `both` (build log #69). User 2026-11-28: "Why can't we have a special test mode that
runs both?"; "Fail if either fails (Recommended)"; every disagreement logged."""
from __future__ import annotations

import json
import logging

import pytest

from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_mode import (BOTH, ReviewerBackendFactory, ReviewerChoice, ReviewerProfile,
                                                      ReviewPacket, Verdict, load_reviewer_profiles)
from planning_system.local_client.review_mode.reviewer_backends import CompareReviewerBackend, merge_verdicts
from planning_system.local_client.review_mode.reviewer_backends.fakes import (FakeReviewerBackend, turn_reply,
                                                                              verdict_json)
from planning_system.local_client.review_worker import ReviewWorker
from planning_system.model_calls import FakeOneShotModelCall, ModelEndpointFactory

PACKET = ReviewPacket.from_json({
    "review_id": "rev-c", "node_title": "report output", "node_context_summary": "", "claim_tag": "technical",
    "claim_text": "Reports are CSV [ref-1:1-1]. They go to S3. Daily runs.",
    "citations": [{"citation": "[ref-1:1-1]", "origin": "user_exchange", "quoted_text": "Write CSV reports.",
                   "pre_text": "", "full_text": ""}]})
NODE_PACKET = ReviewPacket.from_json({"review_id": "rev-n", "node_title": "T", "node_context_summary": "s",
                                      "claim_tag": "", "claim_text": "", "citations": [], "kind": "node",
                                      "content_items": [{"reference_id": "ref-2", "tags": ["technical"],
                                                         "text": "Reports are CSV."}]})
NO = '{"answer": "no", "reason": ""}'


def bulk(unsupported, title=None):
    return json.dumps({"unsupported": [{"sentence": n, "reason": r} for n, r in unsupported],
                       "suggested_title": title})


def factory(model_call=None, workers=None):
    endpoints = ModelEndpointFactory.__new__(ModelEndpointFactory)
    endpoints.create = lambda name, model=None: model_call

    def worker(model):
        built = ReviewWorker(FakeAiCliAdapter(reply=lambda handle, prompt: turn_reply()), reviewer_model_name=model,
                             allowed_tool_names=[])
        if workers is not None:
            workers.append(built)
        return built
    return ReviewerBackendFactory(review_worker_factory=worker, model_endpoints=endpoints)


def test_profiles_and_flag_accept_both():
    profiles = load_reviewer_profiles(environ={})
    assert profiles.get("haiku-compare") == ReviewerProfile("haiku-compare", "claude_code", "haiku", BOTH)
    assert profiles.get("local-compare").resolved_granularity() == BOTH
    assert ReviewerChoice("haiku", granularity="both").resolve(profiles).resolved_granularity() == BOTH


def test_local_llm_both_runs_each_method_in_its_own_fresh_conversation_and_fails_if_either_fails():
    model_call = FakeOneShotModelCall(['{"ready": true}', NO, NO, NO, '{"suggested_title": null}',   # per_sentence
                                       bulk([(2, "S3 not mentioned")], "csv reports")])               # bulk
    backend = factory(model_call).create("local_llm", granularity="both")
    assert isinstance(backend, CompareReviewerBackend)
    verdict = backend.review(PACKET)
    assert verdict == Verdict(False, "[per_sentence] all 3 sentences supported; "
                                     "[bulk] sentence 2 unsupported: S3 not mentioned", "csv reports")
    assert len(model_call.requests) == 6
    assert len(model_call.requests[5].messages) == 1          # bulk started fresh: no per_sentence history


def test_both_pass_means_pass():
    model_call = FakeOneShotModelCall(['{"ready": true}', NO, NO, NO, '{"suggested_title": null}', bulk([])])
    assert factory(model_call).create("local_llm", granularity="both").review(PACKET).passed


def test_claude_code_both_uses_two_reviewer_sessions():
    workers = []
    backend = factory(workers=workers).create("claude_code", "haiku", "both")
    assert backend.review(PACKET).passed
    assert len(workers) == 2 and workers[0] is not workers[1]
    sessions = [w._current_handle.session_id for w in workers]
    assert sessions[0] != sessions[1]


def test_node_reviews_run_one_method_only():
    model_call = FakeOneShotModelCall(['{"guesses": []}'])
    factory(model_call).create("local_llm", granularity="both").review(NODE_PACKET)
    assert len(model_call.requests) == 1


def test_disagreement_is_logged_and_observed(caplog):
    seen = []
    backend = CompareReviewerBackend([("per_sentence", FakeReviewerBackend([verdict_json(True, "fine")])),
                                      ("bulk", FakeReviewerBackend([verdict_json(False, "S3")]))],
                                     observer=lambda verdicts, agreed: seen.append((verdicts, agreed)))
    with caplog.at_level(logging.WARNING):
        verdict = backend.review(PACKET)
    assert verdict == Verdict(False, "[per_sentence] fine; [bulk] S3")
    assert seen[0][1] is False and set(seen[0][0]) == {"per_sentence", "bulk"}
    assert "disagree" in caplog.text


def test_merge_keeps_first_title_and_needs_two_runs():
    assert merge_verdicts({"a": Verdict(True, "x"), "b": Verdict(True, "y", "t")}) == Verdict(True, "[a] x; [b] y", "t")
    with pytest.raises(ValueError):
        CompareReviewerBackend([("only", FakeReviewerBackend())])
