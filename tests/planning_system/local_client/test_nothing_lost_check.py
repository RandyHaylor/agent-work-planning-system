"""Nothing-lost check (build log #60 (2)): for requirement and decision claims the reviewer also asks whether the
restatement drops or weakens any condition, limit, exception or hedge in the cited user quote (or the approved
proposal shown as PRE-INPUT CONTEXT). Any yes fails, naming it. per_sentence: one extra turn after the sentences;
bulk: an extra field in the single answer."""
from __future__ import annotations

import json

import pytest

from planning_system.local_client.review_mode import ReviewPacket, UnparseableVerdict, Verdict
from planning_system.local_client.review_mode.bulk_review import BulkReview
from planning_system.local_client.review_mode.review_conversation import ReviewConversation
from planning_system.local_client.review_mode.sentence_review import SentenceBySentenceReview


class Scripted(ReviewConversation):
    def __init__(self, *answers):
        self.answers, self.turns = list(answers), []

    def say(self, text):
        self.turns.append(text)
        return self.answers.pop(0)


def packet(tag):
    return ReviewPacket.from_json({
        "review_id": "rev-n", "node_title": "notifications", "node_context_summary": "", "claim_tag": tag,
        "claim_text": "Notifications are in-app [ref-u:2-2].",
        "citations": [{"citation": "[ref-u:2-2]", "origin": "user_exchange", "quoted_text": "In-app only for now.",
                       "pre_text": "How should users be notified?",
                       "full_text": "How should users be notified?\nIn-app only for now."}]})


READY, NO, TITLE_OK = '{"ready": true}', '{"answer": "no", "reason": ""}', '{"suggested_title": null}'


def yes(reason):
    return json.dumps({"answer": "yes", "reason": reason})


@pytest.mark.parametrize("tag", ["requirement", "decision"])
def test_per_sentence_asks_one_extra_turn_after_the_sentences(tag):
    conversation = Scripted(READY, NO, yes("drops 'only for now'"), TITLE_OK)
    verdict = SentenceBySentenceReview().run(packet(tag), conversation)
    assert verdict == Verdict(False, "nothing lost check failed: drops 'only for now'")
    nothing_lost_turn = conversation.turns[2]
    for expected in ("drop or weaken", "condition, limit, exception or hedge", "PRE-INPUT CONTEXT"):
        assert expected in nothing_lost_turn
    assert "notifications" in conversation.turns[3]                 # title turn still last


def test_per_sentence_nothing_lost_no_passes():
    verdict = SentenceBySentenceReview().run(packet("requirement"), Scripted(READY, NO, NO, TITLE_OK))
    assert verdict == Verdict(True, "all 1 sentences supported; nothing lost")


def test_per_sentence_failures_are_combined():
    verdict = SentenceBySentenceReview().run(packet("requirement"),
                                             Scripted(READY, yes("S3 not stated"), yes("drops 'for now'"), TITLE_OK))
    assert verdict.reason == "sentence 1 unsupported: S3 not stated; nothing lost check failed: drops 'for now'"


@pytest.mark.parametrize("tag", ["technical", "documentation", "plan", "note"])
def test_other_tags_get_no_nothing_lost_turn(tag):
    conversation = Scripted(READY, NO, TITLE_OK)
    assert SentenceBySentenceReview().run(packet(tag), conversation).passed
    assert len(conversation.turns) == 3


def bulk(unsupported=(), dropped=None, title=None):
    answer = {"unsupported": [{"sentence": n, "reason": r} for n, r in unsupported], "suggested_title": title}
    if dropped is not None:
        answer["dropped_conditions"] = [{"condition": c, "reason": r} for c, r in dropped]
    return json.dumps(answer)


def test_bulk_asks_for_dropped_conditions_in_the_single_turn():
    conversation = Scripted(bulk(dropped=[("only for now", "claim says in-app with no time limit")]))
    verdict = BulkReview().run(packet("decision"), conversation)
    assert verdict == Verdict(False, "nothing lost check failed: only for now: claim says in-app with no time limit")
    assert len(conversation.turns) == 1
    assert "dropped_conditions" in conversation.turns[0] and "condition, limit, exception or hedge" in \
        conversation.turns[0]


def test_bulk_nothing_lost_empty_list_passes():
    assert BulkReview().run(packet("requirement"), Scripted(bulk(dropped=[]))) == \
        Verdict(True, "all 1 sentences supported; nothing lost")


def test_bulk_missing_field_for_requirement_is_unparseable():
    with pytest.raises(UnparseableVerdict):
        BulkReview().run(packet("requirement"), Scripted(bulk()))


def test_bulk_other_tags_do_not_ask():
    conversation = Scripted(bulk())
    assert BulkReview().run(packet("technical"), conversation) == Verdict(True, "all 1 sentences supported")
    assert "dropped_conditions" not in conversation.turns[0]
