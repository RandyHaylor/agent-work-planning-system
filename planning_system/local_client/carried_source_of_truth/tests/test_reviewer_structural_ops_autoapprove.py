"""Structural ops (reparent / remove / reorder_children) carry no citation, so the
citation/title-oriented reviewer must NOT be asked to fact-check them -- doing so
made a lifecycle reparent impossible in live mode (rejected for "no cited slice").
They are auto-approved; only add/add_group/modify_reference reach the LLM, and
content-op verdict indices map back to original change-set positions."""
from __future__ import annotations

import json

from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_modification_reviewer import request_change_set_review


class _RaisingReviewerLifecycle:
    """Fails the test if the LLM is invoked (it must not be for all-structural sets)."""
    def send_prompt_with_rotation_on_exhaustion(self, prompt_text):
        raise AssertionError("LLM reviewer must not be called for an all-structural change-set")


class _CannedReviewerLifecycle:
    def __init__(self, response_text):
        self._response_text = response_text
        self.received_prompt = None
    def send_prompt_with_rotation_on_exhaustion(self, prompt_text):
        self.received_prompt = prompt_text
        return self._response_text


def test_all_structural_change_set_is_auto_approved_without_calling_llm():
    change_set = {"operations": [
        {"op": "reparent", "node_id": "5", "new_parent_id": "f"},
        {"op": "remove", "node_id": "9"},
        {"op": "reorder_children", "parent_id": "e", "child_order": ["2", "3"]},
    ]}
    verdict = request_change_set_review(_RaisingReviewerLifecycle(), change_set, "p-struct")
    assert verdict.approved is True
    assert [v.operation_index for v in verdict.per_operation_verdicts] == [0, 1, 2]
    assert all(v.approved for v in verdict.per_operation_verdicts)


def test_mixed_change_set_reviews_only_content_op_and_remaps_indices():
    project_id = "p-mixed"
    log_result = append_submission_to_raw_input_log(project_id, "sess", "use postgres", "")
    raw_input_id = log_result["raw_input_id"]

    # Original order: structural op FIRST (index 0), content add SECOND (index 1).
    change_set = {"operations": [
        {"op": "reparent", "node_id": "5", "new_parent_id": "f"},
        {"op": "add", "parent_id": "0",
         "raw_input_reference": {"raw_input_id": raw_input_id},
         "short_neutral_title": "db choice"},
    ]}
    # The add is the ONLY op sent to the LLM, so it is content-space index 0.
    canned = _CannedReviewerLifecycle(json.dumps({
        "ops": [{"index": 0, "approved": True, "reason": "clear requirement"}],
        "message": "ok",
    }))
    verdict = request_change_set_review(canned, change_set, project_id)

    assert verdict.approved is True
    by_index = {v.operation_index: v for v in verdict.per_operation_verdicts}
    assert set(by_index) == {0, 1}
    assert by_index[0].approved is True  # structural reparent, auto-approved
    assert "structural" in by_index[0].reason.lower()
    assert by_index[1].approved is True  # the add, approved by the (canned) LLM
    # The reparent op must not have been put in front of the LLM.
    assert "reparent" not in canned.received_prompt


def test_content_op_rejection_still_fails_overall_but_structural_stays_approved():
    project_id = "p-reject"
    log_result = append_submission_to_raw_input_log(project_id, "sess", "thinking out loud", "")
    raw_input_id = log_result["raw_input_id"]
    change_set = {"operations": [
        {"op": "add", "parent_id": "0",
         "raw_input_reference": {"raw_input_id": raw_input_id},
         "short_neutral_title": "noise"},
        {"op": "reparent", "node_id": "5", "new_parent_id": "f"},
    ]}
    canned = _CannedReviewerLifecycle(json.dumps({
        "ops": [{"index": 0, "approved": False, "reason": "not a requirement"}],
        "message": "rejected one",
    }))
    verdict = request_change_set_review(canned, change_set, project_id)
    by_index = {v.operation_index: v for v in verdict.per_operation_verdicts}
    assert verdict.approved is False          # overall fails (content op rejected)
    assert by_index[0].approved is False      # the add
    assert by_index[1].approved is True       # the reparent still auto-approved
