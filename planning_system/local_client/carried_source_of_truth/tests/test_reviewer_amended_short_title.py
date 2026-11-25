"""T8: reviewer can return amended_short_title per op; controlled API persists it."""
from __future__ import annotations

import json
from unittest.mock import patch

from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    save_project_settings,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_modification_reviewer import (
    PerOperationVerdict,
    ReviewerVerdict,
    _parse_per_operation_verdicts,
)
from source_of_truth.requirements_tree_controlled_api import (
    RequirementsTreeControlledApi,
)
from source_of_truth.requirements_tree_store import load_requirements_tree


class _FakeAdapter:
    def open_session_with_initial_user_message(self, *a, **kw):
        return type("S", (), {"session_id": "fake-rev"})()
    def resume_session_with_user_message(self, *a, **kw):
        return ""
    def close_session(self, *a, **kw):
        pass


def test_per_op_verdict_parser_extracts_amended_short_title_when_present():
    payload = {
        "ops": [
            {"index": 0, "approved": True, "reason": "ok",
             "amended_short_title": "vendor placement"},
            {"index": 1, "approved": True, "reason": "ok"},
        ],
    }
    parsed = _parse_per_operation_verdicts(payload, total_operation_count=2)
    assert len(parsed) == 2
    assert parsed[0].amended_short_title == "vendor placement"
    assert parsed[1].amended_short_title is None


def test_controlled_api_applies_amended_title_in_persisted_tree(monkeypatch):
    # Pin the legacy synchronous reviewer (bool OFF) so this test keeps covering
    # the inline amended-title path; the default is title-only non-blocking.
    import source_of_truth.load_config as load_config
    monkeypatch.setattr(load_config, "REVIEWER_TITLE_ONLY_NONBLOCKING", False)
    save_project_settings(ProjectSettings(
        project_id="p-amend",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    log_result = append_submission_to_raw_input_log(
        "p-amend", "session-x", "yes and also never blocked", ""
    )
    raw_input_id = log_result["raw_input_id"]

    fake_verdict = ReviewerVerdict(
        approved=True,
        message="ok",
        per_operation_verdicts=[
            PerOperationVerdict(
                operation_index=0, approved=True, reason="ok",
                amended_short_title="vendor placement",
            )
        ],
        raw_response_text="",
    )
    with patch(
        "source_of_truth.requirements_tree_controlled_api.request_change_set_review",
        return_value=fake_verdict,
    ):
        api = RequirementsTreeControlledApi("p-amend", _FakeAdapter())
        result = api.submit_requirements_tree_change_set({
            "operations": [{
                "op": "add",
                "parent_id": "0",
                "raw_input_reference": {"raw_input_id": raw_input_id},
                "short_neutral_title": "vendor placement on even floors with stair exclusion",
            }],
        })
    assert result.approved is True
    persisted = load_requirements_tree("p-amend")
    persisted_titles = [n.short_neutral_title for n in persisted.nodes_by_id.values()]
    assert "vendor placement" in persisted_titles
    assert "vendor placement on even floors with stair exclusion" not in persisted_titles
