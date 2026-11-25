"""The per-turn UserPromptSubmit guidance must push the agent to capture explicit
instructions/decisions/answers under the pending-instructions group, and must point
at that group's actual node id (resolved from the scaffolded tree)."""
from __future__ import annotations

from source_of_truth import cli_entrypoint
from source_of_truth.requirements_tree_node_schema import PENDING_INSTRUCTIONS_GROUP_TITLE


def test_guidance_names_must_capture_and_pending_instructions_group_id():
    project_id = session_id = "sess-guidance"
    cli_entrypoint._handle_init_and_register([session_id, "/tmp/g.jsonl"])

    pending_id = cli_entrypoint._find_group_id_by_title(project_id, PENDING_INSTRUCTIONS_GROUP_TITLE)
    assert pending_id is not None  # scaffold seeds the group

    guidance = cli_entrypoint._build_per_turn_additional_context_line(project_id, raw_input_id=7)

    assert "pending-instructions" in guidance
    # Judgement-not-checklist framing; corrections/notes not excluded outright.
    assert "living project doc" in guidance
    assert "corrections and notes CAN be requirements" in guidance
    assert "MUST capture" in guidance
    # Confirm-vague-first + nest-refinements-as-children (working-memory usage).
    assert "is it this: xyz" in guidance
    assert "CHILD" in guidance
    # Standing prune/maintain duty: review for conflicts, deprecate stale nodes.
    assert "MAINTAIN" in guidance
    assert "supersedes" in guidance
    # Points at the real group id (nd- prefixed) and the correct raw_input_id.
    assert f"--add 7 --parent nd-{pending_id}" in guidance
    assert "completed-instructions" in guidance
    assert "deprecated-instructions" in guidance
    # Manage as an automatic background task: no id-chatter, no asking the user
    # to do bookkeeping; involve the user only for detail/conflict resolution.
    assert "MANAGE" in guidance
    assert "automatic background task" in guidance
    assert "Do NOT expose node/raw ids" in guidance
    assert "conflict between existing requirements" in guidance
    assert "REQUIRED" in guidance
