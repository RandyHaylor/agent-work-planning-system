"""Public API surface exposed to the primary AI agent.

All mutations go through submit_requirements_tree_change_set, which:
  1. Validates references against the raw log.
  2. Asks the reviewer subagent for approval.
  3. Applies the change-set and writes the new tree atomically (only on approval).

Read endpoints (search, get_node_by_id, get_top_level_node) are unrestricted.
add_project_path / remove_project_path mutate the special project-paths node
WITHOUT going through the reviewer (paths are facts, validated by os.path.exists).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from .ai_cli_adapter_interface import AiCliAdapterInterface
from . import load_config
from .load_config import (
    INTERACTION_TIME_AGENT_GUIDANCE,
    REVIEWER_MODE_DEFER_UNTIL_FLUSH,
    REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    project_reviewer_thinking_log_file_path,
    resolve_effective_global_settings,
    resolve_reviewer_mode_for_project,
)
from . import background_title_reviewer
from .conversation_context_injector import build_top_level_injection_text_for_project
from .deferred_change_sets_queue import (
    append_change_set_to_deferred_queue,
    count_pending_deferred_change_sets,
    read_and_clear_all_deferred_change_sets,
)
from .pending_messages_for_raw_input_sender import add_pending_message_for_raw_input_sender
from .requirements_modification_reviewer import (
    ReviewerVerdict,
    request_change_set_review,
)
from .requirements_reference_validator import (
    ReferenceValidationError,
    validate_change_set_references,
)
from .requirements_tree_change_set_applier import (
    ChangeSetApplicationError,
    apply_change_set_to_tree,
    apply_change_set_to_tree_with_per_op_isolation,
)
from .requirements_tree_change_set_schema import RequirementsTreeChangeSet
from .requirements_tree_node_schema import (
    PROJECT_PATHS_SPECIAL_NODE_KIND,
    TOP_LEVEL_PARENT_SENTINEL,
    RequirementsTree,
    RequirementsTreeNode,
)
from .requirements_tree_store import (
    load_requirements_tree,
    save_requirements_tree_atomically,
)
from .reviewer_session_lifecycle_manager import ReviewerSessionLifecycleManager


@dataclass
class ChangeSetSubmissionResult:
    approved: bool
    reviewer_message: str
    applied_operation_count: int
    message_for_raw_input_sender: str = ""
    reviewer_thinking_log_path: str = ""
    agent_guidance: str = INTERACTION_TIME_AGENT_GUIDANCE
    # Compact "<parent_id>><assigned_id>: <title>" lines, one per add/add_group op
    # that successfully created a node. Empty for change-sets with no creation ops.
    assigned_node_ids: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.assigned_node_ids is None:
            self.assigned_node_ids = []


def _format_node_display_line(node: RequirementsTreeNode, cited_text: "str | None") -> str:
    """Human display per the id-display convention.

    Quote-reference node: `nd-<id>: <title> - raw-<rid>: <cited_text>`.
    Group / project-paths node (no raw ref): `nd-<id>: <title>`.
    """
    from .id_display import format_node_id_for_display, format_raw_input_id_for_display

    title = node.short_neutral_title if node.short_neutral_title else node.kind
    base = f"{format_node_id_for_display(node.node_id)}: {title}"
    reference = node.raw_input_reference
    if reference is None:
        return base
    raw_label = format_raw_input_id_for_display(reference.raw_input_id)
    if cited_text is None:
        return f"{base} - {raw_label}"
    return f"{base} - {raw_label}: {cited_text}"


def _format_assigned_node_lines_from_per_op_outcomes(
    per_op_outcomes: list[dict[str, Any]],
) -> list[str]:
    formatted_lines: list[str] = []
    for outcome in per_op_outcomes:
        if not outcome.get("applied"):
            continue
        if outcome.get("assigned_node_id") is None:
            continue
        from .id_display import format_node_id_for_display
        formatted_lines.append(
            f"{format_node_id_for_display(outcome['assigned_node_parent_id'])}>"
            f"{format_node_id_for_display(outcome['assigned_node_id'])}: "
            f"{outcome['assigned_node_title']}"
        )
    return formatted_lines


class RequirementsTreeControlledApi:
    def __init__(self, project_id: str, ai_cli_adapter: AiCliAdapterInterface) -> None:
        self._project_id = project_id
        self._reviewer_lifecycle = ReviewerSessionLifecycleManager(project_id, ai_cli_adapter)

    def _effective_interaction_guidance(self) -> str:
        """Project override of the agent-guidance text if set, else global default."""
        return resolve_effective_global_settings(self._project_id).interaction_time_agent_guidance

    def _resolve_cited_text_or_placeholder(self, node):
        """The verbatim text a node cites (submission slice + its selected agent
        pre-text), so `read` shows what was actually said -- not just a pointer.
        None for non-quote nodes (groups / project-paths)."""
        reference = node.raw_input_reference
        if reference is None:
            return None
        from .raw_input_log_reader import (
            CharRangeOutOfBoundsError,
            RawLogEntryNotFoundError,
            resolve_quote_text_from_reference,
        )
        char_range_tuple = tuple(reference.char_range) if reference.char_range is not None else None
        try:
            return resolve_quote_text_from_reference(
                self._project_id,
                reference.raw_input_id,
                char_range_tuple,
                reference.pre_text_line_range,
            )
        except (RawLogEntryNotFoundError, CharRangeOutOfBoundsError, ValueError) as exc:
            return f"(resolve error: {exc})"

    # ----- Read endpoints -----

    def get_top_level_node(self) -> str:
        return build_top_level_injection_text_for_project(self._project_id)

    def get_node_by_id(
        self, node_id, include_children: bool = True
    ) -> Optional[dict[str, Any]]:
        tree = load_requirements_tree(self._project_id)
        node = tree.nodes_by_id.get(str(node_id))
        if node is None:
            return None
        cited_text = self._resolve_cited_text_or_placeholder(node)
        result: dict[str, Any] = {
            "node": node.to_json_dict(),
            "cited_text": cited_text,
            "display": _format_node_display_line(node, cited_text),
            "agent_guidance": self._effective_interaction_guidance(),
        }
        if include_children:
            result["children"] = [
                tree.nodes_by_id[cid].to_json_dict()
                for cid in node.child_node_ids
                if cid in tree.nodes_by_id
            ]
        return result

    def search_requirements_nodes(self, query: str) -> dict[str, Any]:
        from .raw_input_log_reader import resolve_quote_text_from_reference
        tree = load_requirements_tree(self._project_id)
        query_lowered = query.lower()
        matches: list[dict[str, Any]] = []
        for node in tree.nodes_by_id.values():
            if node.raw_input_reference is None:
                if any(query_lowered in p.lower() for p in node.project_paths):
                    match_payload = node.to_json_dict()
                    match_payload["display"] = _format_node_display_line(node, None)
                    matches.append(match_payload)
                continue
            try:
                quote_text = resolve_quote_text_from_reference(
                    self._project_id,
                    node.raw_input_reference.raw_input_id,
                    tuple(node.raw_input_reference.char_range)  # type: ignore[arg-type]
                    if node.raw_input_reference.char_range else None,
                    node.raw_input_reference.pre_text_line_range,
                )
            except Exception:
                continue
            if query_lowered in quote_text.lower():
                match_payload = node.to_json_dict()
                match_payload["cited_text"] = quote_text  # show WHAT matched, not just the pointer
                match_payload["display"] = _format_node_display_line(node, quote_text)
                matches.append(match_payload)
        return {"matches": matches, "agent_guidance": self._effective_interaction_guidance()}

    # ----- Mutating endpoints -----

    def submit_requirements_tree_change_set(
        self, change_set_json_dict: dict[str, Any]
    ) -> ChangeSetSubmissionResult:
        result = self._submit_requirements_tree_change_set_impl(change_set_json_dict)
        result.agent_guidance = self._effective_interaction_guidance()
        return result

    def _submit_requirements_tree_change_set_impl(
        self, change_set_json_dict: dict[str, Any]
    ) -> ChangeSetSubmissionResult:
        change_set = RequirementsTreeChangeSet.from_json_dict(change_set_json_dict)
        thinking_log_path = str(project_reviewer_thinking_log_file_path(self._project_id))
        operation_count = len(change_set.operations)

        try:
            validate_change_set_references(self._project_id, change_set.operations)
        except ReferenceValidationError as exc:
            rejection_message = (
                f"{operation_count} requirement op(s) REJECTED at local validation "
                f"(no reviewer call): {exc}"
            )
            add_pending_message_for_raw_input_sender(rejection_message, target_project_id=self._project_id)
            return ChangeSetSubmissionResult(
                approved=False,
                reviewer_message=f"Reference validation failed: {exc}",
                applied_operation_count=0,
                message_for_raw_input_sender=f"[source-of-truth] {rejection_message}",
                reviewer_thinking_log_path=thinking_log_path,
            )

        active_reviewer_mode = resolve_reviewer_mode_for_project(self._project_id)

        # MODE: no reviewer -- apply directly after local validation only.
        if active_reviewer_mode == REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY:
            return self._apply_change_set_directly_with_no_reviewer(change_set, thinking_log_path)

        # MODE: deferred -- queue and return immediately; reviewer runs at flush time.
        if active_reviewer_mode == REVIEWER_MODE_DEFER_UNTIL_FLUSH:
            append_change_set_to_deferred_queue(self._project_id, change_set.to_json_dict())
            queue_depth_after_append = count_pending_deferred_change_sets(self._project_id)
            user_message = (
                f"{operation_count} requirement op(s) DEFERRED for batched review "
                f"(queue depth now {queue_depth_after_append}). "
                f"Call flush_deferred_change_sets_for_review() when planning is done."
            )
            add_pending_message_for_raw_input_sender(user_message, target_project_id=self._project_id)
            return ChangeSetSubmissionResult(
                approved=False,
                reviewer_message="deferred — not yet reviewed",
                applied_operation_count=0,
                message_for_raw_input_sender=f"[source-of-truth] {user_message}",
                reviewer_thinking_log_path=thinking_log_path,
            )

        # DEFAULT (bool ON): title-only, never-reject, non-blocking. Apply every
        # op immediately, then detach a background title review. Only the LIVE
        # mode is affected; none / deferred handled above.
        if load_config.REVIEWER_TITLE_ONLY_NONBLOCKING:
            return self._apply_all_ops_and_spawn_background_title_review(
                change_set, thinking_log_path
            )

        # MODE: live -- contact reviewer now.
        in_flight_user_message = (
            f"Submitting {operation_count} requirement op(s) to the reviewer agent. "
            f"Live reviewer thoughts stream to: {thinking_log_path}"
        )
        add_pending_message_for_raw_input_sender(in_flight_user_message, target_project_id=self._project_id)

        verdict: ReviewerVerdict = request_change_set_review(
            self._reviewer_lifecycle, change_set.to_json_dict(), self._project_id
        )
        approved_indices = verdict.approved_operation_indices()
        rejected_with_reasons = verdict.rejected_operation_indices_with_reasons()

        # If no per-op verdicts at all, fail the whole batch.
        if not verdict.per_operation_verdicts:
            rejection_message = (
                f"{operation_count} requirement op(s) REJECTED by reviewer "
                f"(no per-op verdicts returned). Notes: {verdict.message}. "
                f"Full thoughts: {thinking_log_path}"
            )
            add_pending_message_for_raw_input_sender(rejection_message, target_project_id=self._project_id)
            return ChangeSetSubmissionResult(
                approved=False,
                reviewer_message=verdict.message,
                applied_operation_count=0,
                message_for_raw_input_sender=f"[source-of-truth] {rejection_message}",
                reviewer_thinking_log_path=thinking_log_path,
            )

        # Apply reviewer-provided amended_short_title to each approved op before
        # building the apply list, so the persisted node carries the more-generic
        # title the reviewer asked for.
        amended_title_by_op_index = {
            v.operation_index: v.amended_short_title
            for v in verdict.per_operation_verdicts
            if v.approved and v.amended_short_title
        }
        approved_operations_in_original_order = []
        for op_index in sorted(approved_indices):
            op_dict = dict(change_set.operations[op_index])
            if op_index in amended_title_by_op_index:
                op_dict["short_neutral_title"] = amended_title_by_op_index[op_index]
            approved_operations_in_original_order.append(op_dict)

        # Apply approved ops one at a time so a single bad op doesn't sink
        # the others. Returns per-op outcomes so we can tell the agent which
        # one failed and why.
        apply_failure_summary_text = ""
        applied_operation_count_after_isolation = 0
        assigned_node_lines_for_live_path: list[str] = []
        if approved_operations_in_original_order:
            current_tree = load_requirements_tree(self._project_id)
            new_tree, per_op_outcomes = apply_change_set_to_tree_with_per_op_isolation(
                current_tree, approved_operations_in_original_order
            )
            save_requirements_tree_atomically(new_tree)
            assigned_node_lines_for_live_path = _format_assigned_node_lines_from_per_op_outcomes(
                per_op_outcomes
            )
            applied_operation_count_after_isolation = sum(
                1 for outcome in per_op_outcomes if outcome["applied"]
            )
            apply_failures = [outcome for outcome in per_op_outcomes if not outcome["applied"]]
            if apply_failures:
                apply_failure_summary_text = " Apply failures: " + "; ".join(
                    f"op[{outcome['operation_index']}]: {outcome['error']}"
                    for outcome in apply_failures
                )

        rejection_summary_text = ""
        if rejected_with_reasons:
            rejection_summary_text = " Rejected ops: " + "; ".join(
                f"op[{i}]: {reason}" for i, reason in rejected_with_reasons
            )
        every_op_landed = (
            applied_operation_count_after_isolation == operation_count
            and not rejected_with_reasons
        )
        outcome_message = (
            f"Reviewer applied {applied_operation_count_after_isolation}/{operation_count} op(s). "
            f"Notes: {verdict.message}."
            f"{rejection_summary_text}{apply_failure_summary_text} "
            f"Thoughts log: {thinking_log_path}"
        )
        add_pending_message_for_raw_input_sender(outcome_message, target_project_id=self._project_id)
        return ChangeSetSubmissionResult(
            approved=every_op_landed,
            reviewer_message=verdict.message + rejection_summary_text + apply_failure_summary_text,
            applied_operation_count=applied_operation_count_after_isolation,
            message_for_raw_input_sender=f"[source-of-truth] {outcome_message}",
            reviewer_thinking_log_path=thinking_log_path,
            assigned_node_ids=assigned_node_lines_for_live_path,
        )

    def flush_deferred_change_sets_for_review(self) -> ChangeSetSubmissionResult:
        result = self._flush_deferred_change_sets_for_review_impl()
        result.agent_guidance = self._effective_interaction_guidance()
        return result

    def _flush_deferred_change_sets_for_review_impl(self) -> ChangeSetSubmissionResult:
        """Drain the deferred queue, merge into one change-set, run live review, apply on approval."""
        thinking_log_path = str(project_reviewer_thinking_log_file_path(self._project_id))
        drained_entries = read_and_clear_all_deferred_change_sets(self._project_id)
        if not drained_entries:
            empty_message = "No deferred change-sets to flush; queue is empty."
            return ChangeSetSubmissionResult(
                approved=True,
                reviewer_message=empty_message,
                applied_operation_count=0,
                message_for_raw_input_sender=f"[source-of-truth] {empty_message}",
                reviewer_thinking_log_path=thinking_log_path,
            )

        merged_operations: list[dict[str, Any]] = []
        per_entry_rationales: list[str] = []
        for entry in drained_entries:
            cs = entry.get("change_set", {})
            merged_operations.extend(cs.get("operations", []))
            rationale = cs.get("submitter_rationale", "").strip()
            if rationale:
                per_entry_rationales.append(f"- queued {entry.get('queued_at_iso')}: {rationale}")
        merged_change_set_payload = {
            "operations": merged_operations,
            "submitter_rationale": (
                f"Flushed batch of {len(drained_entries)} deferred change-sets totaling "
                f"{len(merged_operations)} ops.\n" + "\n".join(per_entry_rationales)
            ).strip(),
        }
        operation_count = len(merged_operations)

        in_flight_user_message = (
            f"Flushing {len(drained_entries)} deferred change-set(s) ({operation_count} ops total) "
            f"to the reviewer agent. Live thoughts: {thinking_log_path}"
        )
        add_pending_message_for_raw_input_sender(in_flight_user_message, target_project_id=self._project_id)

        verdict: ReviewerVerdict = request_change_set_review(
            self._reviewer_lifecycle, merged_change_set_payload, self._project_id
        )
        if not verdict.per_operation_verdicts:
            rejection_message = (
                f"Flushed batch of {operation_count} op(s) REJECTED by reviewer "
                f"(no per-op verdicts). Notes: {verdict.message}. Thoughts: {thinking_log_path}"
            )
            add_pending_message_for_raw_input_sender(rejection_message, target_project_id=self._project_id)
            return ChangeSetSubmissionResult(
                approved=False,
                reviewer_message=verdict.message,
                applied_operation_count=0,
                message_for_raw_input_sender=f"[source-of-truth] {rejection_message}",
                reviewer_thinking_log_path=thinking_log_path,
            )

        approved_indices_for_flush = sorted(verdict.approved_operation_indices())
        rejected_with_reasons_for_flush = verdict.rejected_operation_indices_with_reasons()
        approved_operations_for_flush = [
            merged_operations[i] for i in approved_indices_for_flush
        ]

        applied_operation_count_for_flush = 0
        apply_failure_summary_text_for_flush = ""
        assigned_node_lines_for_flush_path: list[str] = []
        if approved_operations_for_flush:
            current_tree = load_requirements_tree(self._project_id)
            new_tree, per_op_outcomes_for_flush = apply_change_set_to_tree_with_per_op_isolation(
                current_tree, approved_operations_for_flush
            )
            save_requirements_tree_atomically(new_tree)
            assigned_node_lines_for_flush_path = _format_assigned_node_lines_from_per_op_outcomes(
                per_op_outcomes_for_flush
            )
            applied_operation_count_for_flush = sum(
                1 for outcome in per_op_outcomes_for_flush if outcome["applied"]
            )
            flush_apply_failures = [
                outcome for outcome in per_op_outcomes_for_flush if not outcome["applied"]
            ]
            if flush_apply_failures:
                apply_failure_summary_text_for_flush = " Apply failures: " + "; ".join(
                    f"op[{outcome['operation_index']}]: {outcome['error']}"
                    for outcome in flush_apply_failures
                )

        rejection_summary_text_for_flush = ""
        if rejected_with_reasons_for_flush:
            rejection_summary_text_for_flush = " Rejected ops: " + "; ".join(
                f"op[{i}]: {reason}" for i, reason in rejected_with_reasons_for_flush
            )
        every_op_landed_in_flush = (
            applied_operation_count_for_flush == operation_count
            and not rejected_with_reasons_for_flush
        )
        approval_message = (
            f"Flushed batch: applied {applied_operation_count_for_flush}/{operation_count} op(s). "
            f"Notes: {verdict.message}."
            f"{rejection_summary_text_for_flush}{apply_failure_summary_text_for_flush} "
            f"Thoughts log: {thinking_log_path}"
        )
        add_pending_message_for_raw_input_sender(approval_message, target_project_id=self._project_id)
        return ChangeSetSubmissionResult(
            approved=every_op_landed_in_flush,
            reviewer_message=verdict.message + rejection_summary_text_for_flush + apply_failure_summary_text_for_flush,
            applied_operation_count=applied_operation_count_for_flush,
            message_for_raw_input_sender=f"[source-of-truth] {approval_message}",
            reviewer_thinking_log_path=thinking_log_path,
            assigned_node_ids=assigned_node_lines_for_flush_path,
        )

    def _apply_change_set_directly_with_no_reviewer(
        self, change_set: RequirementsTreeChangeSet, thinking_log_path: str,
    ) -> ChangeSetSubmissionResult:
        operation_count = len(change_set.operations)
        try:
            current_tree = load_requirements_tree(self._project_id)
            new_tree, per_op_outcomes_for_no_reviewer = apply_change_set_to_tree_with_per_op_isolation(
                current_tree, change_set.operations
            )
            # In no-reviewer mode the contract is "all-or-nothing local application";
            # if any op failed isolation we surface the first error.
            failures = [o for o in per_op_outcomes_for_no_reviewer if not o["applied"]]
            if failures:
                raise ChangeSetApplicationError(failures[0]["error"])
            save_requirements_tree_atomically(new_tree)
        except ChangeSetApplicationError as exc:
            error_message = (
                f"{operation_count} op(s) FAILED to apply (no-reviewer mode): {exc}"
            )
            add_pending_message_for_raw_input_sender(error_message, target_project_id=self._project_id)
            return ChangeSetSubmissionResult(
                approved=False,
                reviewer_message=str(exc),
                applied_operation_count=0,
                message_for_raw_input_sender=f"[source-of-truth] {error_message}",
                reviewer_thinking_log_path=thinking_log_path,
            )
        assigned_node_lines_for_no_reviewer = _format_assigned_node_lines_from_per_op_outcomes(
            per_op_outcomes_for_no_reviewer
        )
        approval_message = (
            f"{operation_count} op(s) APPLIED (no-reviewer mode — no human/AI review performed)."
        )
        add_pending_message_for_raw_input_sender(approval_message, target_project_id=self._project_id)
        return ChangeSetSubmissionResult(
            approved=True,
            reviewer_message="no-reviewer mode: applied without review",
            applied_operation_count=operation_count,
            message_for_raw_input_sender=f"[source-of-truth] {approval_message}",
            reviewer_thinking_log_path=thinking_log_path,
            assigned_node_ids=assigned_node_lines_for_no_reviewer,
        )

    def _apply_all_ops_and_spawn_background_title_review(
        self, change_set: RequirementsTreeChangeSet, thinking_log_path: str,
    ) -> ChangeSetSubmissionResult:
        """Title-only non-blocking default: apply every op now (never reject),
        then detach a background title review over the newly-created nodes.

        Structural *apply* validity still governs whether an op lands (a missing
        parent still fails as an apply error); that is NOT a review rejection.
        """
        operation_count = len(change_set.operations)
        current_tree = load_requirements_tree(self._project_id)
        new_tree, per_op_outcomes = apply_change_set_to_tree_with_per_op_isolation(
            current_tree, change_set.operations
        )
        save_requirements_tree_atomically(new_tree)

        assigned_node_lines = _format_assigned_node_lines_from_per_op_outcomes(per_op_outcomes)
        applied_operation_count = sum(1 for o in per_op_outcomes if o["applied"])
        created_node_ids = [
            str(o["assigned_node_id"])
            for o in per_op_outcomes
            if o.get("applied") and o.get("assigned_node_id") is not None
        ]

        apply_failure_summary_text = ""
        apply_failures = [o for o in per_op_outcomes if not o["applied"]]
        if apply_failures:
            apply_failure_summary_text = " Apply failures: " + "; ".join(
                f"op[{o['operation_index']}]: {o['error']}" for o in apply_failures
            )

        if created_node_ids:
            background_title_reviewer.spawn_background_title_review(
                self._project_id, created_node_ids
            )

        title_review_note = (
            " Title review queued in background; any title generalizations will be "
            "reported on your next turn."
            if created_node_ids
            else ""
        )
        outcome_message = (
            f"{applied_operation_count}/{operation_count} op(s) applied immediately "
            f"(title-only non-blocking reviewer)."
            f"{apply_failure_summary_text}{title_review_note}"
        )
        add_pending_message_for_raw_input_sender(outcome_message, target_project_id=self._project_id)
        return ChangeSetSubmissionResult(
            approved=(applied_operation_count == operation_count),
            reviewer_message="title-only non-blocking: applied immediately, title review backgrounded"
            + apply_failure_summary_text,
            applied_operation_count=applied_operation_count,
            message_for_raw_input_sender=f"[source-of-truth] {outcome_message}",
            reviewer_thinking_log_path=thinking_log_path,
            assigned_node_ids=assigned_node_lines,
        )

    def rename_node_title(self, node_id: str, new_title: str) -> bool:
        """Set a node's title and trigger the SAME backgrounded title review.

        Accepts an nd-prefixed or bare id. Returns False if the node is unknown.
        """
        from .id_display import strip_node_id_input_prefix

        normalized_node_id = strip_node_id_input_prefix(node_id)
        tree = load_requirements_tree(self._project_id)
        node = tree.nodes_by_id.get(normalized_node_id)
        if node is None:
            return False
        node.short_neutral_title = new_title
        save_requirements_tree_atomically(tree)
        background_title_reviewer.spawn_background_title_review(
            self._project_id, [normalized_node_id]
        )
        return True

    def add_project_path(self, filesystem_path: str) -> bool:
        if not os.path.exists(filesystem_path):
            raise ValueError(f"Refusing to add non-existent path: {filesystem_path}")
        tree = load_requirements_tree(self._project_id)
        project_paths_node = self._find_or_create_project_paths_node(tree)
        if filesystem_path in project_paths_node.project_paths:
            return False
        project_paths_node.project_paths.append(filesystem_path)
        save_requirements_tree_atomically(tree)
        return True

    def remove_project_path(self, filesystem_path: str) -> bool:
        tree = load_requirements_tree(self._project_id)
        project_paths_node = self._find_project_paths_node_or_none(tree)
        if project_paths_node is None or filesystem_path not in project_paths_node.project_paths:
            return False
        project_paths_node.project_paths.remove(filesystem_path)
        save_requirements_tree_atomically(tree)
        return True

    # ----- internal helpers -----

    def _find_project_paths_node_or_none(
        self, tree: RequirementsTree
    ) -> Optional[RequirementsTreeNode]:
        for node_id in tree.list_top_level_node_ids():
            node = tree.nodes_by_id.get(node_id)
            if node is not None and node.kind == PROJECT_PATHS_SPECIAL_NODE_KIND:
                return node
        return None

    def _find_or_create_project_paths_node(
        self, tree: RequirementsTree
    ) -> RequirementsTreeNode:
        existing = self._find_project_paths_node_or_none(tree)
        if existing is not None:
            return existing
        new_node_id_string = str(tree.next_node_id)
        tree.next_node_id += 1
        new_node = RequirementsTreeNode(
            node_id=new_node_id_string,
            parent_id=TOP_LEVEL_PARENT_SENTINEL,
            kind=PROJECT_PATHS_SPECIAL_NODE_KIND,
            short_neutral_title="project paths",
        )
        tree.nodes_by_id[new_node_id_string] = new_node
        return new_node
