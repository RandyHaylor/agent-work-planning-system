"""SentenceBySentenceReview (build log #55): code splits the claim; every sentence is asked, in one conversation;
any "yes" (unsupported claim) fails the review; the title turn only suggests."""
from __future__ import annotations

import json

import pytest

from planning_system.local_client.review_mode import ReviewPacket, UnparseableVerdict, Verdict
from planning_system.local_client.review_mode.review_conversation import ReviewConversation
from planning_system.local_client.review_mode.reviewer_backends.conversations import TranscriptReplayConversation
from planning_system.local_client.review_mode.sentence_review import SentenceBySentenceReview
from planning_system.local_client.review_mode.sentence_splitter import SentenceSplitter


class ScriptedConversation(ReviewConversation):
    def __init__(self, answers):
        self.answers, self.turns = list(answers), []

    def say(self, text):
        self.turns.append(text)
        return self.answers.pop(0)


def packet(claim, tag="technical"):
    return ReviewPacket.from_json({
        "review_id": "rev-9", "node_title": "report output", "node_context_summary": "reports",
        "claim_tag": tag, "claim_text": claim,
        "citations": [{"citation": "[ref-1:1-1]", "origin": "user_exchange", "quoted_text": "Write CSV reports.",
                       "pre_text": "", "full_text": ""}]})


def yes(reason):
    return json.dumps({"answer": "yes", "reason": reason})


NO = json.dumps({"answer": "no", "reason": ""})
READY = '{"ready": true}'
TITLE_OK = '{"suggested_title": null}'


def test_every_sentence_is_asked_in_order_in_one_conversation():
    conversation = ScriptedConversation([READY, NO, NO, NO, TITLE_OK])
    claim = "Reports are CSV [ref-1:1-1]. They go to S3. TODO: confirm with ops."
    assert SentenceBySentenceReview().run(packet(claim), conversation) == Verdict(True, "all 3 sentences supported")
    assert conversation.turns[0].startswith("NEW REVIEW rev-9")
    assert 'Sentence 1 of 3: "Reports are CSV [ref-1:1-1]."' in conversation.turns[1]
    assert 'Sentence 2 of 3: "They go to S3."' in conversation.turns[2]
    assert 'Sentence 3 of 3: "TODO: confirm with ops."' in conversation.turns[3]
    assert '"report output"' in conversation.turns[4]


def test_any_yes_fails_and_names_each_failing_sentence():
    conversation = ScriptedConversation([READY, NO, yes("S3 not in any reference"), NO, TITLE_OK])
    verdict = SentenceBySentenceReview().run(packet("Reports are CSV. They go to S3. Daily."), conversation)
    assert verdict == Verdict(False, "sentence 2 unsupported: S3 not in any reference")


def test_yes_without_reason_quotes_the_sentence():
    conversation = ScriptedConversation([READY, '{"answer": "YES"}', TITLE_OK])
    verdict = SentenceBySentenceReview().run(packet("They go to S3."), conversation)
    assert verdict == Verdict(False, "sentence 1 unsupported: They go to S3.")


def test_title_suggestion_is_carried_on_pass_and_fail():
    conversation = ScriptedConversation([READY, NO, '{"suggested_title": "report format"}'])
    assert SentenceBySentenceReview().run(packet("Reports are CSV."), conversation) == \
        Verdict(True, "all 1 sentences supported", "report format")


def test_answer_wrapped_in_prose_is_read_from_the_last_object():
    conversation = ScriptedConversation([READY, 'Thinking... {"answer": "no", "reason": ""} done', TITLE_OK])
    assert SentenceBySentenceReview().run(packet("Reports are CSV."), conversation).passed


@pytest.mark.parametrize("bad", ["I think it is fine.", '{"answer": "maybe"}', '{"passed": true, "reason": "x"}'])
def test_unreadable_sentence_answer_raises(bad):
    with pytest.raises(UnparseableVerdict):
        SentenceBySentenceReview().run(packet("Reports are CSV."), ScriptedConversation([READY, bad, TITLE_OK]))


def test_unreadable_title_answer_raises():
    with pytest.raises(UnparseableVerdict):
        SentenceBySentenceReview().run(packet("Reports are CSV."), ScriptedConversation([READY, NO, "fine"]))


def test_empty_claim_fails_without_asking_the_model():
    conversation = ScriptedConversation([])
    assert SentenceBySentenceReview().run(packet("   "), conversation) == \
        Verdict(False, "claim has no sentences to review")
    assert conversation.turns == []


def test_splitter_keeps_abbreviations_versions_and_citation_markers_whole():
    text = "Use httpx 0.27 e.g. for fetching; retries are 3 [ref-2:10-12]. The API v2.1 returns JSON. Ask U.S. ops."
    assert SentenceSplitter().split(text) == [
        "Use httpx 0.27 e.g. for fetching; retries are 3 [ref-2:10-12].", "The API v2.1 returns JSON.",
        "Ask U.S. ops."]


def test_transcript_replay_carries_earlier_turns_into_each_prompt():
    prompts = []
    conversation = TranscriptReplayConversation(lambda prompt: prompts.append(prompt) or f"a{len(prompts)}")
    conversation.say("first")
    conversation.say("second")
    assert prompts[0] == "first"
    assert "YOU WERE TOLD:\nfirst\nYOU ANSWERED:\na1" in prompts[1] and prompts[1].endswith("NOW:\nsecond")
