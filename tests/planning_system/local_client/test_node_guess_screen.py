"""Whole-node guess screen (build log #60 (5)): ONE check over the whole node (title + summary + every content
item + all their resolved references) listing every statement the writer would have had to guess (prompt V4 of
planning/experiments/node_validation/run.py, adapted). Findings fail the node review with a reason per statement.
Node packets go to the screen whatever the content-review granularity."""
from __future__ import annotations

import json

import pytest

from planning_system.local_client.review_mode import ReviewPacket, UnparseableVerdict, Verdict
from planning_system.local_client.review_mode.kind_dispatch import ReviewByKind
from planning_system.local_client.review_mode.node_guess_screen import NodeGuessScreen
from planning_system.local_client.review_mode.review_conversation import ReviewConversation
from planning_system.local_client.review_mode.reviewer_backends import ReviewerBackendFactory
from planning_system.model_calls import FakeOneShotModelCall, ModelEndpointFactory

NODE = ReviewPacket.from_json({
    "review_id": "rev-node", "kind": "node", "node_title": "session handling",
    "node_context_summary": "How login sessions work.", "claim_tag": "", "claim_text": "",
    "content_items": [
        {"reference_id": "ref-a", "tags": ["requirement"],
         "text": "Sessions expire after 30 minutes of inactivity [ref-u:2-2]. Tokens are stored with keyring."},
        {"reference_id": "ref-b", "tags": ["open_items"], "text": "RESEARCH: keyring backends\nASK USER: remember me"}],
    "citations": [{"citation": "[ref-u:2-2]", "origin": "user_exchange", "quoted_text": "After 30 minutes of inactivity.",
                   "pre_text": "When should sessions expire?", "full_text": ""}]})


class Scripted(ReviewConversation):
    def __init__(self, *answers):
        self.answers, self.turns, self.max_tokens = list(answers), [], []

    def say(self, text, max_tokens=None):
        self.turns.append(text)
        self.max_tokens.append(max_tokens)
        return self.answers.pop(0)


def guesses(*items):
    return json.dumps({"guesses": [{"statement": n, "why": why} for n, why in items]})


def test_one_turn_numbers_every_statement_of_the_whole_node():
    conversation = Scripted(guesses())
    assert NodeGuessScreen().run(NODE, conversation) == Verdict(True, "no guessed statements in 6")
    [turn] = conversation.turns
    for expected in ("NEW REVIEW rev-node", "would have had to guess", "1. [title] session handling",
                     "2. [context summary] How login sessions work.",
                     "3. [ref-a requirement] Sessions expire after 30 minutes of inactivity [ref-u:2-2].",
                     "4. [ref-a requirement] Tokens are stored with keyring.",
                     "5. [ref-b open_items] RESEARCH: keyring backends", "6. [ref-b open_items] ASK USER: remember me",
                     "PRE-INPUT CONTEXT", "After 30 minutes of inactivity.", '"guesses"'):
        assert expected in turn
    assert conversation.max_tokens == [800]


def test_findings_fail_with_a_reason_per_statement():
    verdict = NodeGuessScreen().run(NODE, Scripted(guesses((4, "keyring not in any reference"), (2, "no source"))))
    assert verdict == Verdict(False, 'statement 2 guessed ([context summary] "How login sessions work."): no source; '
                                     'statement 4 guessed ([ref-a requirement] "Tokens are stored with keyring."): '
                                     "keyring not in any reference")


@pytest.mark.parametrize("answer", ["nothing guessed", json.dumps({"guesses": [{"statement": 9}]}),
                                    json.dumps({"verdict": "ok"})])
def test_unreadable_answer_raises(answer):
    with pytest.raises(UnparseableVerdict):
        NodeGuessScreen().run(NODE, Scripted(answer))


def test_review_by_kind_routes_node_packets_to_the_screen():
    calls = []

    class Recording:
        def __init__(self, name):
            self.name = name

        def run(self, packet, conversation):
            calls.append(self.name)
            return Verdict(True, self.name)

    method = ReviewByKind(Recording("content"), Recording("node"))
    method.run(NODE, Scripted())
    method.run(ReviewPacket.from_json({"review_id": "r", "claim_tag": "technical", "claim_text": "x"}), Scripted())
    assert calls == ["node", "content"]


def test_local_llm_backend_screens_a_node_in_one_call_with_room_for_the_list():
    model_call = FakeOneShotModelCall([guesses((4, "keyring not in any reference"))])
    endpoints = ModelEndpointFactory.__new__(ModelEndpointFactory)
    endpoints.create = lambda name, model=None: model_call
    verdict = ReviewerBackendFactory(model_endpoints=endpoints).create("local_llm").review(NODE)
    assert not verdict.passed and "statement 4 guessed" in verdict.reason
    assert len(model_call.requests) == 1 and model_call.requests[0].max_tokens == 800
