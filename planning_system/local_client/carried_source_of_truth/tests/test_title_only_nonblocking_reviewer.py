"""Default reviewer: title-only, never-reject, non-blocking (backgrounded)."""
from __future__ import annotations

from source_of_truth.ai_cli_adapter_interface import (
    AiCliAdapterInterface,
    PersistentReviewerSessionHandle,
)
import source_of_truth.load_config as load_config
from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    save_project_settings,
)
from source_of_truth.pending_messages_for_raw_input_sender import (
    show_pending_messages_to_raw_input_sender_for_project,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_controlled_api import (
    RequirementsTreeControlledApi,
)
from source_of_truth.requirements_tree_store import load_requirements_tree
import source_of_truth.background_title_reviewer as background_title_reviewer


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


def _seed_raw(project_id: str, text: str = "use the npm package manager") -> int:
    return append_submission_to_raw_input_log(project_id, "s", text, "")["raw_input_id"]


def _add_op(raw_input_id: int, title: str) -> dict:
    return {
        "submitter_rationale": "t",
        "operations": [{
            "op": "add",
            "parent_id": "0",
            "raw_input_reference": {"raw_input_id": raw_input_id},
            "short_neutral_title": title,
        }],
    }


def test_specific_title_op_applies_immediately_and_spawns_background_review(monkeypatch):
    # default is ON; do not actually spawn.
    captured: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        background_title_reviewer,
        "spawn_background_title_review",
        lambda project_id, node_ids: captured.append((project_id, list(node_ids))),
    )
    save_project_settings(ProjectSettings(
        project_id="p-nb",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    raw_id = _seed_raw("p-nb")
    api = RequirementsTreeControlledApi("p-nb", _StubAdapter())
    result = api.submit_requirements_tree_change_set(
        _add_op(raw_id, "Use npm package manager")
    )

    # Applied immediately: op present in the tree right away.
    assert result.applied_operation_count == 1
    titles = [n.short_neutral_title for n in load_requirements_tree("p-nb").nodes_by_id.values()]
    assert "Use npm package manager" in titles
    # Background title review was invoked with the created node id.
    assert len(captured) == 1
    assert captured[0][0] == "p-nb"
    assert len(captured[0][1]) == 1


def test_never_rejects_op_legacy_reviewer_would_reject(monkeypatch):
    monkeypatch.setattr(
        background_title_reviewer, "spawn_background_title_review",
        lambda project_id, node_ids: None,
    )
    save_project_settings(ProjectSettings(
        project_id="p-noreject",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    # An "agent prose" cited slice the legacy reviewer would reject.
    raw_id = _seed_raw("p-noreject", "let me think about this out loud")
    api = RequirementsTreeControlledApi("p-noreject", _StubAdapter())
    result = api.submit_requirements_tree_change_set(
        _add_op(raw_id, "some title")
    )
    assert result.approved is True
    assert result.applied_operation_count == 1


def test_run_title_review_generalizes_title_and_enqueues_note(monkeypatch):
    monkeypatch.setattr(
        background_title_reviewer, "spawn_background_title_review",
        lambda project_id, node_ids: None,
    )
    save_project_settings(ProjectSettings(
        project_id="p-rev",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    raw_id = _seed_raw("p-rev")
    api = RequirementsTreeControlledApi("p-rev", _StubAdapter())
    api.submit_requirements_tree_change_set(_add_op(raw_id, "Use npm package manager"))
    # Drain the application note so we can assert only on the generalize note later.
    show_pending_messages_to_raw_input_sender_for_project("p-rev")

    created_id = next(
        n.node_id for n in load_requirements_tree("p-rev").nodes_by_id.values()
        if n.short_neutral_title == "Use npm package manager"
    )

    def stub_model_caller(prompt_text: str) -> str:
        return (
            '{"titles": [{"node_id": "%s", '
            '"generalized_title": "package manager selection"}]}' % created_id
        )

    notes = background_title_reviewer.run_title_review_and_enqueue_notes(
        "p-rev", [created_id], stub_model_caller
    )
    assert len(notes) == 1
    assert "package manager selection" in notes[0]
    assert "generalized to" in notes[0]
    # Tree title was updated.
    titles = [n.short_neutral_title for n in load_requirements_tree("p-rev").nodes_by_id.values()]
    assert "package manager selection" in titles
    assert "Use npm package manager" not in titles
    # The note landed in the pending-message queue.
    drained = show_pending_messages_to_raw_input_sender_for_project("p-rev")
    assert any("package manager selection" in m["message_text"] for m in drained)


def test_run_title_review_unchanged_title_enqueues_no_note(monkeypatch):
    monkeypatch.setattr(
        background_title_reviewer, "spawn_background_title_review",
        lambda project_id, node_ids: None,
    )
    save_project_settings(ProjectSettings(
        project_id="p-unchanged",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    raw_id = _seed_raw("p-unchanged")
    api = RequirementsTreeControlledApi("p-unchanged", _StubAdapter())
    api.submit_requirements_tree_change_set(_add_op(raw_id, "package manager selection"))
    show_pending_messages_to_raw_input_sender_for_project("p-unchanged")
    created_id = next(
        n.node_id for n in load_requirements_tree("p-unchanged").nodes_by_id.values()
        if n.short_neutral_title == "package manager selection"
    )

    def echo_model_caller(prompt_text: str) -> str:
        return (
            '{"titles": [{"node_id": "%s", '
            '"generalized_title": "package manager selection"}]}' % created_id
        )

    notes = background_title_reviewer.run_title_review_and_enqueue_notes(
        "p-unchanged", [created_id], echo_model_caller
    )
    assert notes == []


def test_rename_node_updates_title_and_triggers_background_review(monkeypatch):
    captured: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        background_title_reviewer, "spawn_background_title_review",
        lambda project_id, node_ids: captured.append((project_id, list(node_ids))),
    )
    save_project_settings(ProjectSettings(
        project_id="p-rename",
        reviewer_mode_override=REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    ))
    raw_id = _seed_raw("p-rename")
    api = RequirementsTreeControlledApi("p-rename", _StubAdapter())
    api.submit_requirements_tree_change_set(_add_op(raw_id, "old title"))
    created_id = next(
        n.node_id for n in load_requirements_tree("p-rename").nodes_by_id.values()
        if n.short_neutral_title == "old title"
    )
    captured.clear()

    # Accepts an nd- prefixed id.
    ok = api.rename_node_title(f"nd-{created_id}", "Use npm package manager")
    assert ok is True
    titles = [n.short_neutral_title for n in load_requirements_tree("p-rename").nodes_by_id.values()]
    assert "Use npm package manager" in titles
    assert captured == [("p-rename", [created_id])]
