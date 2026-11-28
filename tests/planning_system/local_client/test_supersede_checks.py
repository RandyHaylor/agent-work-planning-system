"""Supersede model checks on review-mode clients (05-spec-reference-supersede.md, approved changes (a) and (b)):
- TrialReview: does the claim still hold in the newer copy? Shown the diff-matched lines AND the whole newer copy;
  a deprecation or warning counts as no longer supported (experiment prompt P3 + the approved rule).
- QuoteCheck: ONE call listing every cited user quote (experiment prompt Q2), batched when there are many;
  changed quotes come back as findings (reference ids)."""
from __future__ import annotations

import json

import pytest

from planning_system.local_client.review_mode import ReviewPacket, UnparseableVerdict, Verdict
from planning_system.local_client.review_mode.kind_dispatch import ReviewByKind
from planning_system.local_client.review_mode.quote_check import QuoteCheck
from planning_system.local_client.review_mode.review_conversation import ReviewConversation
from planning_system.local_client.review_mode.trial_review import TrialReview


class Scripted(ReviewConversation):
    def __init__(self, *answers):
        self.answers, self.turns, self.max_tokens = list(answers), [], []

    def say(self, text, max_tokens=None):
        self.turns.append(text)
        self.max_tokens.append(max_tokens)
        return self.answers.pop(0)


TRIAL = ReviewPacket.from_json({
    "review_id": "rev-t", "kind": "trial", "node_title": "cache lifetime", "node_context_summary": "",
    "claim_tag": "documentation", "claim_text": "Entries expire after 72 hours [ref-old:2-2].",
    "citations": [{"citation": {"reference_id": "ref-old", "start_line": 2, "end_line": 2}, "origin": "document",
                   "quoted_text": "Entries expire after seventy two hours."}],
    "against_reference_id": "ref-new", "against_text": "Cache guide\nEntries expire after one day.\nDeprecated: TTL.",
    "comparisons": [{"citation": {"reference_id": "ref-old", "start_line": 2, "end_line": 2},
                     "old_text": "Entries expire after seventy two hours.",
                     "new_text": "Entries expire after one day."}]})


def trial_answer(still, broken=False, reason="r"):
    return json.dumps({"still_supported": still, "broken_page": broken, "reason": reason})


def test_trial_shows_old_lines_matched_lines_and_the_whole_new_copy_in_one_turn():
    conversation = Scripted(trial_answer(False, reason="now one day"))
    assert TrialReview().run(TRIAL, conversation) == Verdict(False, "no longer supported by ref-new: now one day")
    [turn] = conversation.turns
    for expected in ("NEW REVIEW rev-t", "CLAIM: Entries expire after 72 hours [ref-old:2-2].",
                     "CITED OLD LINES:\nEntries expire after seventy two hours.",
                     "THE SAME LINES IN THE NEW COPY (matched by diff):\nEntries expire after one day.",
                     "WHOLE NEW COPY:\nCache guide", "A deprecation or warning about the claimed thing",
                     '"still_supported"', '"broken_page"'):
        assert expected in turn


def test_trial_pass_and_broken_page():
    assert TrialReview().run(TRIAL, Scripted(trial_answer(True))) == Verdict(True, "still supported by ref-new: r")
    assert TrialReview().run(TRIAL, Scripted(trial_answer(True, broken=True, reason="login page"))) == \
        Verdict(False, "the new copy ref-new looks like an error or placeholder page: login page")


def test_trial_unreadable_answer_raises():
    with pytest.raises(UnparseableVerdict):
        TrialReview().run(TRIAL, Scripted('{"supported": true}'))


def quote(i, text, pre="Q?"):
    return {"citation": {"reference_id": f"ref-q{i}", "start_line": 2, "end_line": 2}, "origin": "user_exchange",
            "quoted_text": text, "pre_text": pre}


def quote_packet(count):
    return ReviewPacket.from_json({
        "review_id": "rev-q", "kind": "quote_check", "node_title": "", "node_context_summary": "", "claim_tag": "",
        "claim_text": "", "against_reference_id": "ref-new",
        "subject": quote(0, "Make it 24 hours.", "Is 72 hours still right?") | {
            "citation": {"reference_id": "ref-new", "start_line": 2, "end_line": 2}},
        "citations": [quote(i, f"answer {i}") for i in range(1, count + 1)]})


def changed(*items):
    return json.dumps({"changed": [{"quote": q, "reason": r} for q, r in items]})


def test_quote_check_lists_every_quote_in_one_call_and_returns_findings():
    conversation = Scripted(changed(("U2", "replaces 72 with 24")))
    verdict = QuoteCheck().run(quote_packet(3), conversation)
    assert verdict == Verdict(False, "changes U2 (ref-q2): replaces 72 with 24", None, ("ref-q2",))
    [turn] = conversation.turns
    for expected in ('Agent asked: "Is 72 hours still right?"\nUser answered: "Make it 24 hours."',
                     '[U1] agent asked: "Q?" / user answered: "answer 1"', "[U3]", "narrows, widens",
                     '"changed"'):
        assert expected in turn
    assert conversation.max_tokens == [600]


def test_quote_check_no_change_passes():
    assert QuoteCheck().run(quote_packet(2), Scripted(changed())) == Verdict(True, "changes none of 2 earlier quotes")


def test_quote_check_batches_large_projects_and_keeps_numbering():
    conversation = Scripted(changed(), changed(("U45", "contradicts")))
    verdict = QuoteCheck(batch_size=40).run(quote_packet(45), conversation)
    assert len(conversation.turns) == 2 and "[U41]" in conversation.turns[1] and "[U40]" not in conversation.turns[1]
    assert verdict.findings == ("ref-q45",)


def test_quote_check_without_earlier_quotes_asks_nothing():
    conversation = Scripted()
    assert QuoteCheck().run(quote_packet(0), conversation).passed and conversation.turns == []


def test_quote_check_unknown_label_is_unparseable():
    with pytest.raises(UnparseableVerdict):
        QuoteCheck().run(quote_packet(2), Scripted(changed(("U9", "x"))))


def test_review_by_kind_routes_trial_and_quote_check():
    seen = []

    class Named:
        def __init__(self, name):
            self.name = name

        def run(self, packet, conversation):
            seen.append(self.name)
            return Verdict(True, self.name)

    method = ReviewByKind(Named("content"), Named("node"), Named("trial"), Named("quote_check"))
    method.run(TRIAL, Scripted())
    method.run(quote_packet(1), Scripted())
    assert seen == ["trial", "quote_check"]
