"""Sends a change-set to the live reviewer session and parses a per-operation verdict.

Reviewer protocol:
  Reply with EXACTLY one JSON object containing one verdict per operation:
    {"ops": [{"index": 0, "approved": true, "reason": "..."},
             {"index": 1, "approved": false, "reason": "..."}],
     "message": "<overall summary, optional>"}
  The "message" field is an overall summary; per-op decisions live in "ops".

Performance note: every raw_input_reference in the change-set is resolved against
the on-disk raw input log and the resolved quote text + pre_submission_content
are inlined directly into the prompt, so the reviewer never needs to invoke
Read tools to verdict. This keeps the round-trip to a single Claude turn.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .raw_input_log_reader import (
    RawLogEntryNotFoundError,
    find_session_id_for_raw_input_id,
    get_raw_log_entry_by_raw_input_id,
    resolve_quote_text_from_reference,
)
from .reviewer_session_lifecycle_manager import ReviewerSessionLifecycleManager


@dataclass
class PerOperationVerdict:
    operation_index: int
    approved: bool
    reason: str = ""
    amended_short_title: "str | None" = None  # if non-None, persist this title instead of submitter's


@dataclass
class ReviewerVerdict:
    approved: bool                      # True iff EVERY op was approved
    message: str                        # overall summary the reviewer wrote
    per_operation_verdicts: list[PerOperationVerdict] = field(default_factory=list)
    raw_response_text: str = ""

    def approved_operation_indices(self) -> list[int]:
        return [v.operation_index for v in self.per_operation_verdicts if v.approved]

    def rejected_operation_indices_with_reasons(self) -> list[tuple[int, str]]:
        return [(v.operation_index, v.reason)
                for v in self.per_operation_verdicts if not v.approved]


def _iter_balanced_brace_object_substrings_from_end(response_text: str):
    """Yield JSON-object substrings from the response, scanned right-to-left.

    For each '}' in the response (last to first), walk left tracking nesting
    depth and yield the substring from the matching '{' through this '}'.
    Skips braces inside JSON strings (handles escaped quotes).
    """
    closing_brace_positions = [i for i, ch in enumerate(response_text) if ch == "}"]
    for closing_index in reversed(closing_brace_positions):
        depth = 0
        inside_string_literal = False
        previous_char = ""
        for scan_index in range(closing_index, -1, -1):
            char_at_scan = response_text[scan_index]
            # Detect entering/leaving a JSON string literal (handle escaped quotes).
            if char_at_scan == '"':
                # Count preceding backslashes to decide if this quote is escaped.
                backslash_run_length = 0
                back = scan_index - 1
                while back >= 0 and response_text[back] == "\\":
                    backslash_run_length += 1
                    back -= 1
                if backslash_run_length % 2 == 0:
                    inside_string_literal = not inside_string_literal
            if inside_string_literal:
                continue
            if char_at_scan == "}":
                depth += 1
            elif char_at_scan == "{":
                depth -= 1
                if depth == 0:
                    yield response_text[scan_index : closing_index + 1]
                    break


def _extract_verdict_json_from_response(response_text: str) -> dict[str, Any]:
    """Find the rightmost valid JSON object in the response that contains 'ops'.

    Robust to: surrounding prose, markdown code fences, example JSON snippets
    embedded earlier in the reply, escaped quotes in string fields.
    """
    for candidate_substring in _iter_balanced_brace_object_substrings_from_end(response_text):
        try:
            parsed = json.loads(candidate_substring)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "ops" in parsed:
            return parsed
    # Fallback: rightmost valid JSON object even without "ops" key, so callers
    # can surface a useful error rather than a generic regex miss.
    for candidate_substring in _iter_balanced_brace_object_substrings_from_end(response_text):
        try:
            parsed = json.loads(candidate_substring)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"No valid JSON object found in reviewer response: {response_text[:300]}")


def _build_inline_resolved_context_for_change_set(
    project_id: str, change_set_json_dict: dict[str, Any]
) -> str:
    inlined_blocks: list[str] = []
    for op_index, operation in enumerate(change_set_json_dict.get("operations", [])):
        ref = operation.get("raw_input_reference")
        if not ref:
            inlined_blocks.append(
                f"--- op[{op_index}] op={operation.get('op')} (no raw_input_reference) ---"
            )
            continue
        raw_input_id = ref["raw_input_id"]
        char_range = tuple(ref["char_range"]) if ref.get("char_range") else None
        pre_text_line_range = ref.get("pre_text_line_range")
        try:
            entry = get_raw_log_entry_by_raw_input_id(project_id, raw_input_id)
            session_id = find_session_id_for_raw_input_id(project_id, raw_input_id)
            quoted_text = resolve_quote_text_from_reference(
                project_id, raw_input_id, char_range, pre_text_line_range
            )
        except (RawLogEntryNotFoundError, ValueError) as exc:
            inlined_blocks.append(
                f"--- op[{op_index}] RESOLUTION ERROR: {exc} ---"
            )
            continue
        inlined_blocks.append(
            f"--- op[{op_index}] op={operation.get('op')} raw_input_id={raw_input_id} session={session_id} ---\n"
            f"PRE-INPUT CONTEXT (what the agent had said before this raw input):\n"
            f"{entry.pre_submission_content}\n"
            f"FULL RAW INPUT:\n{entry.submission_text}\n"
            f"CITED SLICE (what this op claims as the requirement):\n{quoted_text}\n"
        )
    return "\n".join(inlined_blocks)


def _parse_per_operation_verdicts(
    verdict_payload: dict[str, Any], total_operation_count: int
) -> list[PerOperationVerdict]:
    raw_ops = verdict_payload.get("ops")
    if not isinstance(raw_ops, list):
        return []
    parsed: list[PerOperationVerdict] = []
    for raw in raw_ops:
        if not isinstance(raw, dict):
            continue
        index = raw.get("index")
        if not isinstance(index, int) or index < 0 or index >= total_operation_count:
            continue
        amended_title_raw_value = raw.get("amended_short_title")
        amended_short_title = (
            str(amended_title_raw_value)
            if isinstance(amended_title_raw_value, str) and amended_title_raw_value.strip() != ""
            else None
        )
        parsed.append(PerOperationVerdict(
            operation_index=index,
            approved=bool(raw.get("approved", False)),
            reason=str(raw.get("reason", "")),
            amended_short_title=amended_short_title,
        ))
    return parsed


# Structural ops carry NO raw_input_reference and assert no requirement text --
# they only rearrange/remove existing nodes, and the change-set applier validates
# them deterministically (parent exists, child set matches, etc.). There is
# nothing for the citation/title-oriented reviewer to fact-check, so sending them
# to the LLM only produced false rejections ("no cited slice / not a requirement"),
# which made a lifecycle reparent impossible in live mode. We auto-approve them
# instead and only send citation/title ops (add / add_group / modify_reference)
# to the reviewer.
STRUCTURAL_OPS_REQUIRING_NO_REVIEW: frozenset[str] = frozenset(
    {"reparent", "remove", "reorder_children"}
)


TITLE_GENERALIZATION_RULE: str = (
    "A node title must be a SHORT NEUTRAL SUBJECT: a 1-5 word noun phrase naming "
    "the TOPIC only. It must NOT contain specific requirement detail (no values, "
    "no rules, no sentences, no decisions). Examples: 'Use npm package manager' -> "
    "'package manager selection'; 'Vendors only on even floors' -> 'vendor placement'; "
    "'Phrases must be in-character' -> 'phrase character voice'. If a title is already "
    "a short neutral subject, leave it unchanged."
)


def build_title_generalization_prompt(titles_by_node_id: dict[str, str]) -> str:
    """Prompt asking the model to generalize specific titles to neutral subjects.

    Reply contract: EXACTLY one JSON object {"titles": [{"node_id": "<id>",
    "generalized_title": "<short neutral subject>"}, ...]}, one entry per input
    node. If a title is already neutral, echo it unchanged.
    """
    listing = "\n".join(
        f"  {node_id}: {title!r}" for node_id, title in titles_by_node_id.items()
    )
    return (
        "Generalize requirement-tree node TITLES to short neutral subjects.\n"
        f"{TITLE_GENERALIZATION_RULE}\n\n"
        "Reply with EXACTLY one JSON object, nothing before/after, no markdown fence:\n"
        '  {"titles": [{"node_id": "<id>", "generalized_title": "<short neutral subject>"}, ...]}\n'
        "One entry per input node. Echo unchanged titles verbatim.\n\n"
        f"TITLES:\n{listing}"
    )


def parse_generalized_titles_from_response(
    response_text: str, valid_node_ids: "set[str] | None" = None
) -> dict[str, str]:
    """Extract {node_id: generalized_title} from a title-generalization reply.

    Robust to surrounding prose / code fences (reuses the right-to-left balanced
    brace scan). Entries with empty titles, or node_ids not in valid_node_ids
    (when provided), are dropped.
    """
    for candidate_substring in _iter_balanced_brace_object_substrings_from_end(response_text):
        try:
            parsed = json.loads(candidate_substring)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "titles" in parsed:
            break
    else:
        return {}
    out: dict[str, str] = {}
    raw_titles = parsed.get("titles")
    if not isinstance(raw_titles, list):
        return {}
    for raw in raw_titles:
        if not isinstance(raw, dict):
            continue
        node_id = raw.get("node_id")
        generalized = raw.get("generalized_title")
        if not isinstance(node_id, str) or not isinstance(generalized, str):
            continue
        node_id = node_id.strip()
        generalized = generalized.strip()
        if not node_id or not generalized:
            continue
        if valid_node_ids is not None and node_id not in valid_node_ids:
            continue
        out[node_id] = generalized
    return out


def request_change_set_review(
    reviewer_lifecycle: ReviewerSessionLifecycleManager,
    change_set_json_dict: dict[str, Any],
    project_id: str,
) -> ReviewerVerdict:
    all_operations = change_set_json_dict.get("operations", [])
    total_operation_count = len(all_operations)

    # Partition into structural (auto-approved) and content (LLM-reviewed) ops,
    # remembering each content op's ORIGINAL index so verdicts map back correctly.
    structural_verdicts: list[PerOperationVerdict] = []
    content_ops_with_original_index: list[tuple[int, dict[str, Any]]] = []
    for original_index, operation in enumerate(all_operations):
        if operation.get("op") in STRUCTURAL_OPS_REQUIRING_NO_REVIEW:
            structural_verdicts.append(PerOperationVerdict(
                operation_index=original_index,
                approved=True,
                reason="structural op (no citation to review); validated when applied",
            ))
        else:
            content_ops_with_original_index.append((original_index, operation))

    # All-structural change-set: nothing to fact-check, skip the LLM entirely.
    if not content_ops_with_original_index:
        return ReviewerVerdict(
            approved=True,
            message="Structural ops auto-approved (no citations to review).",
            per_operation_verdicts=sorted(
                structural_verdicts, key=lambda v: v.operation_index
            ),
            raw_response_text="",
        )

    content_operations = [op for _, op in content_ops_with_original_index]
    content_change_set = {**change_set_json_dict, "operations": content_operations}
    inline_context = _build_inline_resolved_context_for_change_set(
        project_id, content_change_set
    )
    content_operation_count = len(content_operations)
    prompt_text = (
        "Review fast. One bullet-style fact-check per op, then commit. "
        "Reply with EXACTLY one JSON object, nothing before/after, no markdown fence. "
        "Reason <=15 words. Message <=20 words.\n\n"
        "TITLE RULE for `add` and `add_group` ops: <short_neutral_title> must be a\n"
        "1-5 word NOUN PHRASE naming the TOPIC (1-50 chars). Sentences and rules are\n"
        "wrong shape. Examples:\n"
        "  Good: \"vendor placement\", \"phrase character voice\", \"back end stack\"\n"
        "  Bad shape (sentence/rule): \"Phrases must be in-character\" -> rewrite to\n"
        "    something like \"phrase character voice\".\n"
        "  Bad scope (adds detail not in slice): cited=\"yes [to vendor on even floors]\",\n"
        "    title=\"vendor every other floor with stair exclusion\" -> rewrite to\n"
        "    something like \"vendor placement\".\n"
        "Reject titles that are empty or >50 chars. For wrong-shape or wrong-scope titles,\n"
        "do NOT reject -- set per-op `amended_short_title` to a generic noun-phrase that\n"
        "stays within the cited slice. The amended title is persisted automatically.\n\n"
        "EXPLICITLY-SUPPORTED PATTERNS (do NOT reject for any of these reasons):\n"
        " (1) BRIEF CONFIRMATION: CITED SLICE may be a brief confirmation such as 'yes', "
        "'no', 'A', 'B', 'C', 'go', 'ok', 'do it', etc. The actual requirement is the "
        "conjunction of the agent's question (visible in PRE-INPUT CONTEXT, the ~2000 chars "
        "the agent said immediately before the user submitted) AND the user's confirmation. "
        "APPROVE when PRE-INPUT CONTEXT contains a clear question/proposal and the cited "
        "slice is an unambiguous affirmative/selection answer. Do NOT require the requirement "
        "statement to appear inside the user's submission text.\n"
        " (2) USER STATES THE REQUIREMENT DIRECTLY: if the CITED SLICE itself contains an "
        "unambiguous requirement statement (an instruction, rule, constraint, decision, "
        "preference), APPROVE -- the user is the source of truth. This holds EVEN IF the "
        "user's text partially contradicts, overrides, modifies, or sidesteps the agent's "
        "preceding question/proposal in PRE-INPUT CONTEXT. The pre-input is context, not a "
        "consistency check; user statements supersede prior agent framing. Common shapes: "
        "'yes and also X' / 'yes but X' / 'no, instead do X' / 'actually let's just X'. "
        "Treat the cited slice on its own merits as a requirement, ignore mismatch with "
        "PRE-INPUT CONTEXT.\n"
        "Only reject for substantive defects: cited slice is not actually a requirement "
        "(question, thinking-aloud, reaction with no directive content), char_range cuts "
        "off mid-meaning, or the operation does not match the cited slice.\n\n"
        f"OPS ({content_operation_count}):\n{json.dumps(content_operations, indent=2)}\n\n"
        f"RESOLVED CONTEXT (quotes inlined; no Read needed):\n{inline_context}"
    )
    response_text = reviewer_lifecycle.send_prompt_with_rotation_on_exhaustion(prompt_text)
    try:
        verdict_payload = _extract_verdict_json_from_response(response_text)
    except (ValueError, json.JSONDecodeError) as exc:
        return ReviewerVerdict(
            approved=False,
            message=f"Could not parse reviewer verdict ({exc}); denying by default.",
            per_operation_verdicts=[],
            raw_response_text=response_text,
        )
    # Verdict indices are in CONTENT-op space (0..content_operation_count-1).
    content_verdicts = _parse_per_operation_verdicts(verdict_payload, content_operation_count)
    if not content_verdicts:
        # Reviewer responded with valid JSON but no usable per-op verdicts;
        # fail closed rather than guess.
        return ReviewerVerdict(
            approved=False,
            message=(
                f"Reviewer response missing usable per-op verdicts: "
                f"{verdict_payload.get('message', '')}".strip()
            ),
            per_operation_verdicts=[],
            raw_response_text=response_text,
        )
    # Map content-space verdict indices back to original change-set indices.
    remapped_content_verdicts = [
        PerOperationVerdict(
            operation_index=content_ops_with_original_index[v.operation_index][0],
            approved=v.approved,
            reason=v.reason,
            amended_short_title=v.amended_short_title,
        )
        for v in content_verdicts
    ]
    combined_verdicts = sorted(
        structural_verdicts + remapped_content_verdicts,
        key=lambda v: v.operation_index,
    )
    every_op_approved = (
        len(combined_verdicts) == total_operation_count
        and all(v.approved for v in combined_verdicts)
    )
    return ReviewerVerdict(
        approved=every_op_approved,
        message=str(verdict_payload.get("message", "")),
        per_operation_verdicts=combined_verdicts,
        raw_response_text=response_text,
    )
