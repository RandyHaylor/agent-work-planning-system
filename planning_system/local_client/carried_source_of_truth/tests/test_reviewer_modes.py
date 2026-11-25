"""Cover the three reviewer modes: live, none, deferred."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from source_of_truth.ai_cli_adapter_interface import (
    AiCliAdapterInterface,
    PersistentReviewerSessionHandle,
)
from source_of_truth.load_config import (
    REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    GlobalSettings,
    ProjectSettings,
    save_global_settings,
    save_project_settings,
)
from source_of_truth.deferred_change_sets_queue import (
    count_pending_deferred_change_sets,
    read_and_clear_all_deferred_change_sets,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_controlled_api import (
    RequirementsTreeControlledApi,
)
from source_of_truth.requirements_tree_store import load_requirements_tree


class _StubReviewerHandle(PersistentReviewerSessionHandle):
    @property
    def session_id(self): return "stub-reviewer"
    def send_prompt_and_await_response(self, prompt_text): return ""
    def is_alive(self): return True
    def terminate(self): pass


class _StubAdapter(AiCliAdapterInterface):
    def get_current_session_id(self): return "stub-sess"
    def register_user_prompt_submit_hook(self, hook_callable): pass
    def inject_into_next_user_turn(self, injection_text): pass
    def inject_into_subagent_spawn(self, injection_text): pass
    def spawn_persistent_reviewer_session(self, **kwargs): return _StubReviewerHandle()


def _seed_one_short_raw_entry(project_id: str, session_id: str = "s") -> str:
    log_result = append_submission_to_raw_input_log(project_id, session_id, "yes", "")
    return log_result["raw_input_id"]


def _build_one_op_change_set(raw_input_id: int) -> dict:
    return {
        "submitter_rationale": "test",
        "operations": [{
            "op": "add",
            "parent_id": "0",
            "raw_input_reference": {"raw_input_id": raw_input_id},
            "short_neutral_title": "test top",
        }],
    }


def test_no_reviewer_mode_applies_change_set_directly_without_calling_reviewer():
    save_project_settings(ProjectSettings(
        project_id="p-no-rev",
        reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    entry_id = _seed_one_short_raw_entry("p-no-rev", "s")
    api = RequirementsTreeControlledApi("p-no-rev", _StubAdapter())

    with patch("source_of_truth.requirements_tree_controlled_api.request_change_set_review") as mock_review:
        result = api.submit_requirements_tree_change_set(
            _build_one_op_change_set(entry_id)
        )
        assert mock_review.call_count == 0  # reviewer NEVER called

    assert result.approved is True
    assert result.applied_operation_count == 1
    tree = load_requirements_tree("p-no-rev")
    assert len(tree.nodes_by_id) == 1


def test_deferred_mode_queues_change_set_without_calling_reviewer_or_applying():
    save_project_settings(ProjectSettings(
        project_id="p-defer",
        reviewer_mode_override=REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    ))
    entry_id = _seed_one_short_raw_entry("p-defer", "s")
    api = RequirementsTreeControlledApi("p-defer", _StubAdapter())

    with patch("source_of_truth.requirements_tree_controlled_api.request_change_set_review") as mock_review:
        result = api.submit_requirements_tree_change_set(
            _build_one_op_change_set(entry_id)
        )
        assert mock_review.call_count == 0

    assert result.approved is False
    assert "DEFERRED" in result.message_for_raw_input_sender
    assert count_pending_deferred_change_sets("p-defer") == 1
    tree = load_requirements_tree("p-defer")
    assert len(tree.nodes_by_id) == 0


def test_deferred_flush_calls_reviewer_once_with_merged_ops_and_applies_on_approval():
    from source_of_truth.requirements_modification_reviewer import (
        PerOperationVerdict,
        ReviewerVerdict,
    )

    save_project_settings(ProjectSettings(
        project_id="p-defer-flush",
        reviewer_mode_override=REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    ))
    entry_a = _seed_one_short_raw_entry("p-defer-flush", "s")
    entry_b = _seed_one_short_raw_entry("p-defer-flush", "s")
    api = RequirementsTreeControlledApi("p-defer-flush", _StubAdapter())
    api.submit_requirements_tree_change_set(_build_one_op_change_set(entry_a))
    api.submit_requirements_tree_change_set(_build_one_op_change_set(entry_b))
    assert count_pending_deferred_change_sets("p-defer-flush") == 2

    full_approval_verdict = ReviewerVerdict(
        approved=True, message="ok",
        per_operation_verdicts=[
            PerOperationVerdict(operation_index=0, approved=True),
            PerOperationVerdict(operation_index=1, approved=True),
        ],
        raw_response_text="",
    )
    with patch(
        "source_of_truth.requirements_tree_controlled_api.request_change_set_review",
        return_value=full_approval_verdict,
    ) as mock_review:
        flush_result = api.flush_deferred_change_sets_for_review()

    assert mock_review.call_count == 1
    merged_payload_passed_to_reviewer = mock_review.call_args[0][1]
    assert len(merged_payload_passed_to_reviewer["operations"]) == 2
    assert flush_result.approved is True
    assert flush_result.applied_operation_count == 2
    assert count_pending_deferred_change_sets("p-defer-flush") == 0
    tree = load_requirements_tree("p-defer-flush")
    assert len(tree.nodes_by_id) == 2


def test_deferred_flush_with_empty_queue_returns_no_op_success():
    save_project_settings(ProjectSettings(
        project_id="p-empty-flush",
        reviewer_mode_override=REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    ))
    api = RequirementsTreeControlledApi("p-empty-flush", _StubAdapter())
    with patch("source_of_truth.requirements_tree_controlled_api.request_change_set_review") as mock_review:
        result = api.flush_deferred_change_sets_for_review()
        assert mock_review.call_count == 0
    assert result.approved is True
    assert result.applied_operation_count == 0


def test_deferred_flush_rejection_keeps_tree_unchanged_and_does_not_requeue():
    from source_of_truth.requirements_modification_reviewer import (
        PerOperationVerdict,
        ReviewerVerdict,
    )

    save_project_settings(ProjectSettings(
        project_id="p-defer-reject",
        reviewer_mode_override=REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    ))
    entry_id = _seed_one_short_raw_entry("p-defer-reject", "s")
    api = RequirementsTreeControlledApi("p-defer-reject", _StubAdapter())
    api.submit_requirements_tree_change_set(_build_one_op_change_set(entry_id))

    full_rejection_verdict = ReviewerVerdict(
        approved=False, message="nope",
        per_operation_verdicts=[
            PerOperationVerdict(operation_index=0, approved=False, reason="bad ref"),
        ],
        raw_response_text="",
    )
    with patch(
        "source_of_truth.requirements_tree_controlled_api.request_change_set_review",
        return_value=full_rejection_verdict,
    ):
        result = api.flush_deferred_change_sets_for_review()

    assert result.approved is False
    tree = load_requirements_tree("p-defer-reject")
    assert len(tree.nodes_by_id) == 0
    assert count_pending_deferred_change_sets("p-defer-reject") == 0


def test_partial_per_op_verdicts_apply_only_approved_ops_in_live_mode(monkeypatch):
    """In live mode, when reviewer approves some ops and rejects others, only approved ones land."""
    from source_of_truth.requirements_modification_reviewer import (
        PerOperationVerdict,
        ReviewerVerdict,
    )
    from source_of_truth.load_config import REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT
    import source_of_truth.load_config as load_config
    # Pin the legacy synchronous reviewer (bool OFF) so per-op rejection is still
    # covered; the default reviewer is title-only non-blocking (never rejects).
    monkeypatch.setattr(load_config, "REVIEWER_TITLE_ONLY_NONBLOCKING", False)

    save_project_settings(ProjectSettings(
        project_id="p-partial",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    entry_a = _seed_one_short_raw_entry("p-partial", "s")
    entry_b = _seed_one_short_raw_entry("p-partial", "s")
    entry_c = _seed_one_short_raw_entry("p-partial", "s")
    api = RequirementsTreeControlledApi("p-partial", _StubAdapter())
    three_op_change_set = {
        "submitter_rationale": "test partial",
        "operations": [
            {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": entry_a}, "short_neutral_title": "ta"},
            {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": entry_b}, "short_neutral_title": "tb"},
            {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": entry_c}, "short_neutral_title": "tc"},
        ],
    }
    partial_verdict = ReviewerVerdict(
        approved=False,  # not all approved
        message="approved 2 of 3",
        per_operation_verdicts=[
            PerOperationVerdict(operation_index=0, approved=True),
            PerOperationVerdict(operation_index=1, approved=False, reason="dupe"),
            PerOperationVerdict(operation_index=2, approved=True),
        ],
        raw_response_text="",
    )
    with patch(
        "source_of_truth.requirements_tree_controlled_api.request_change_set_review",
        return_value=partial_verdict,
    ):
        result = api.submit_requirements_tree_change_set(three_op_change_set)

    assert result.approved is False  # not unanimous
    assert result.applied_operation_count == 2
    assert "op[1]: dupe" in result.reviewer_message
    tree = load_requirements_tree("p-partial")
    assert len(tree.nodes_by_id) == 2
