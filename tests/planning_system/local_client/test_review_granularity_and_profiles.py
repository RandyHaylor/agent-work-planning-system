"""Review granularity (per_sentence | bulk) and reviewer profiles (build log #59).
User 2026-11-27: "a reviewer setting to say per sentence or bulk and profiles for different settings, Gemma 4 and
local llm suggestion for per sentence, otherwise bulk"."""
from __future__ import annotations

import json

import pytest

from planning_system.errors import Invalid
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_mode import (ReviewerBackendFactory, ReviewerChoice, ReviewerProfile,
                                                      ReviewPacket, UnparseableVerdict, Verdict,
                                                      load_reviewer_profiles)
from planning_system.local_client.review_mode.bulk_review import BulkReview
from planning_system.local_client.review_mode.review_conversation import ReviewConversation
from planning_system.local_client.review_mode.reviewer_profiles import ReviewerProfiles
from planning_system.local_client.review_worker import ReviewWorker
from planning_system.model_calls import FakeOneShotModelCall, ModelEndpointFactory

PACKET = ReviewPacket.from_json({
    "review_id": "rev-b", "node_title": "report output", "node_context_summary": "", "claim_tag": "requirement",
    "claim_text": "Reports are CSV [ref-1:1-1]. They go to S3. Daily runs.",
    "citations": [{"citation": "[ref-1:1-1]", "origin": "user_exchange", "quoted_text": "Write CSV reports.",
                   "pre_text": "", "full_text": ""}]})


class Scripted(ReviewConversation):
    def __init__(self, *answers):
        self.answers, self.turns = list(answers), []

    def say(self, text):
        self.turns.append(text)
        return self.answers.pop(0)


def bulk(unsupported, title=None):
    return json.dumps({"unsupported": [{"sentence": n, "reason": r} for n, r in unsupported],
                       "suggested_title": title})


# --------------------------------------------------------------------------- bulk review

def test_bulk_asks_once_with_every_numbered_sentence_and_the_title():
    conversation = Scripted(bulk([]))
    assert BulkReview().run(PACKET, conversation) == Verdict(True, "all 3 sentences supported")
    assert len(conversation.turns) == 1
    turn = conversation.turns[0]
    for expected in ("1. Reports are CSV [ref-1:1-1].", "2. They go to S3.", "3. Daily runs.", "report output",
                     "Does this sentence make a claim not fully supported by an included user or document reference?"):
        assert expected in turn


def test_bulk_fails_naming_each_unsupported_sentence_in_order():
    verdict = BulkReview().run(PACKET, Scripted(bulk([(3, "no schedule given"), (2, "S3 not mentioned")],
                                                     "report format")))
    assert verdict == Verdict(False, "sentence 2 unsupported: S3 not mentioned; sentence 3 unsupported: "
                                     "no schedule given", "report format")


@pytest.mark.parametrize("answer", ["looks fine", json.dumps({"unsupported": [{"sentence": 9}]}),
                                    json.dumps({"unsupported": [{"sentence": "2"}]})])
def test_bulk_unreadable_or_out_of_range_answer_raises(answer):
    with pytest.raises(UnparseableVerdict):
        BulkReview().run(PACKET, Scripted(answer))


# --------------------------------------------------------------------------- profiles

PROFILES = ReviewerProfiles({
    "local": ReviewerProfile("local", "local_llm", None, "per_sentence"),
    "haiku": ReviewerProfile("haiku", "claude_code", "haiku", "bulk"),
    "plain": ReviewerProfile("plain", "claude_code")})


def test_default_profile_is_local_per_sentence():
    assert ReviewerChoice().resolve(PROFILES) == ReviewerProfile("local", "local_llm", None, "per_sentence")


def test_flags_override_the_profile():
    resolved = ReviewerChoice("haiku", model="sonnet", granularity="per_sentence").resolve(PROFILES)
    assert (resolved.backend, resolved.model, resolved.resolved_granularity()) == \
        ("claude_code", "sonnet", "per_sentence")


def test_changing_backend_drops_the_profiles_model_and_granularity():
    resolved = ReviewerChoice("haiku", backend="local_llm").resolve(PROFILES)
    assert (resolved.model, resolved.resolved_granularity()) == (None, "per_sentence")


@pytest.mark.parametrize("backend, expected", [("local_llm", "per_sentence"), ("claude_code", "bulk")])
def test_granularity_default_per_backend(backend, expected):
    assert ReviewerProfile("x", backend).resolved_granularity() == expected


def test_unknown_profile_and_granularity_are_invalid():
    with pytest.raises(Invalid):
        ReviewerChoice("nope").resolve(PROFILES)
    with pytest.raises(Invalid):
        ReviewerProfile("x", "local_llm", None, "paragraph").resolved_granularity()


def test_shipped_profiles_file():
    profiles = load_reviewer_profiles(environ={})
    assert profiles.get().backend == "local_llm" and profiles.get().resolved_granularity() == "per_sentence"
    assert profiles.get("haiku").resolved_granularity() == "bulk"


# --------------------------------------------------------------------------- factory wiring

def factory(model_call=None, adapter=None):
    endpoints = ModelEndpointFactory.__new__(ModelEndpointFactory)
    endpoints.create = lambda name, model=None: model_call
    return ReviewerBackendFactory(
        review_worker_factory=lambda model: ReviewWorker(adapter, reviewer_model_name=model, allowed_tool_names=[]),
        model_endpoints=endpoints)


def test_local_llm_reviews_per_sentence_by_default():
    model_call = FakeOneShotModelCall(['{"ready": true}'] + ['{"answer": "no", "reason": ""}'] * 3
                                      + ['{"suggested_title": null}'])
    assert factory(model_call).create("local_llm").review(PACKET).passed
    assert len(model_call.requests) == 5                       # opening + 3 sentences + title


def test_claude_code_reviews_in_bulk_by_default():
    adapter = FakeAiCliAdapter(reply=lambda handle, prompt: bulk([(2, "S3 not mentioned")]))
    verdict = factory(adapter=adapter).create("claude_code").review(PACKET)
    assert verdict == Verdict(False, "sentence 2 unsupported: S3 not mentioned")
    assert len(adapter.sessions[0].prompts) == 2               # priming + one bulk turn


def test_profile_granularity_reaches_the_backend():
    model_call = FakeOneShotModelCall([bulk([])])
    backend = factory(model_call).create_from_profile(ReviewerProfile("lb", "local_llm", None, "bulk"))
    assert backend.review(PACKET).passed and len(model_call.requests) == 1
