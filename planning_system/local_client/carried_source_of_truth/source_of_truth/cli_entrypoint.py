"""Single CLI dispatcher: `source-of-truth <verb>` for ALL operations.

Runtime verbs take NO project id -- the project is resolved from the current
session (CLAUDE_CODE_SESSION_ID). If the session isn't part of a project the
command errors. (An undocumented `--project <id>` override exists for portability.)

Setup verbs (these establish the session<->project link, so they DO take ids):
  init-project              <project_id>
  init-and-register         <session_id> <conversation_path>
  add-session               <project_id> <session_id> <conversation_path>

Runtime verbs (the agent calls these; project comes from the session):
  set-mode                  <live|none|deferred>
  submit-change-set         --add <raw_input_id> --parent <pid_or_letter> --title "<leaf>" [--new-group "<group>"]
  submit-change-set         --add-group --parent <pid_or_letter> --title "<group>"
  submit-change-set         @path/to/changeset.json   |   -   (read JSON from stdin)
  show-tree                 [--show-all]
  read                      <node_id> [<node_id> ...]
  search-nodes              <query>
  list-raw                  (list raw-log entries: raw-<id>: first 30 chars)
  read-raw                  <raw_input_id>   (print one raw-log entry in full)
  pretext                   <node_id> <start> <end> | --all | --none
  flush-deferred
  add-path                  <filesystem_path>
  show-top-level

The single top-level is the project itself; every requirement is a node under it
(use a parent node/group letter id, or "0" only when no fitting parent exists).

Hook entry-point:
  user-prompt-submit-hook   reads JSON from stdin, runs raw log writer,
                            emits {"hookSpecificOutput": {"additionalContext": ...}}
"""
from __future__ import annotations

import json
import os
import sys

from .add_session_to_project_cli import (
    SessionAlreadyInDifferentProjectError,
    add_session_to_project,
)
from .ai_cli_adapter_claude_code import ClaudeCodeAdapter
from .load_config import (
    ALL_VALID_REVIEWER_MODES,
    ensure_root_directories_exist,
    load_project_settings,
    project_directory_for,
    save_project_settings,
)
from .conversation_context_injector import build_top_level_injection_text_for_project
from .project_identifier_resolver import resolve_project_id_for_session
from .raw_input_log_writer import append_submission_to_raw_input_log
from .requirements_tree_controlled_api import RequirementsTreeControlledApi
from .requirements_tree_node_schema import (
    GROUP_NODE_KIND,
    PENDING_INSTRUCTIONS_GROUP_TITLE,
    RequirementsTree,
)
from .requirements_tree_store import (
    load_requirements_tree,
    save_requirements_tree_atomically,
)


def _find_group_id_by_title(project_id: str, group_title: str) -> "str | None":
    """Return the node id of the (first) group node with this title, or None.

    Best-effort: any load problem returns None so the per-turn guidance still
    renders (it just falls back to a 'run show-tree' hint for the id).
    """
    try:
        tree = load_requirements_tree(project_id)
    except Exception:
        return None
    for node in tree.nodes_by_id.values():
        if node.kind == GROUP_NODE_KIND and node.short_neutral_title == group_title:
            return node.node_id
    return None


def _build_per_turn_additional_context_line(project_id: str, raw_input_id: int) -> str:
    """Action-shaped guidance injected on every user prompt.

    The headline rule is MUST-CAPTURE: any explicit instruction, decision, or
    answer to an agent's question is a requirement and has to be stored under the
    pending-instructions group (later reparented to completed-/deprecated-).

    Commands take no project id -- it is resolved from the current session.
    """
    from .id_display import format_node_id_for_display

    pending_id = _find_group_id_by_title(project_id, PENDING_INSTRUCTIONS_GROUP_TITLE)
    pending_parent = (
        format_node_id_for_display(pending_id)
        if pending_id is not None
        else "<pending-instructions id; run show-tree>"
    )
    return (
        f"source-of-truth: prompt logged raw-{raw_input_id}. "
        f"CAPTURE = attach the user's settled requests, decisions, answers, and project facts to this living project doc (judgement, not a checklist). "
        f"A passing question or thinking-aloud usually isn't worth a node, but don't draw hard lines -- corrections and notes CAN be requirements. "
        f"If the prompt is vague or mid-discussion, don't guess -- ask 'is it this: xyz?' and file THEIR reply instead (make xyz precise and narrow). "
        f"A settled instruction/decision/request/answer (e.g. 'do X', 'use library Y', 'make it blue', 'yes', 'option B') you MUST capture -- store it before acting on it. "
        f"If it REFINES a requirement already in the tree, file it as a CHILD of that node (its parent is that requirement's node), NOT a new sibling under pending-instructions: "
        f"source-of-truth submit-change-set --add {raw_input_id} --parent {pending_parent} "
        f"--title \"<noun-phrase TOPIC, 1-50 chars, NOT a sentence>\". "
        f"MAINTAIN -- after capturing, review for conflicts: if this requirement supersedes, changes, or contradicts an existing "
        f"requirement node, reparent the now-stale node to deprecated-instructions (or remove it) so the tree holds ONLY current, "
        f"non-conflicting truth. Prioritize keeping the tree pruned: promptly retire deprecated/superseded entries -- don't let stale ones linger. "
        f"You MANAGE this tree as an automatic background task -- capture, reparent, and prune on your own "
        f"(carried-out instructions -> completed-instructions; superseded/dropped -> deprecated-instructions). "
        f"Do NOT expose node/raw ids to the user or ask them to do tree bookkeeping; you may briefly say you're "
        f"'saving to the source-of-truth tree'. Involve the user ONLY to request missing detail or to resolve a "
        f"genuine conflict between existing requirements. "
        f"Using this tool is REQUIRED: it is your only way to store guaranteed verbatim user quotes as requirements. "
        f"(AskUserQuestion answers are auto-captured the same way; ids display as nd-<node> / raw-<input>, accept prefixed or bare.) "
        f"Other content: file under the best-fit group (parent = a group node id, or '0' for top-level). "
        f"view: source-of-truth show-tree, list-raw; read SKILL.md for more"
    )


def _extract_pre_text_from_transcript_for_prompt(
    transcript_path: "str | None", incoming_prompt_text: str
) -> str:
    """Pre-text = the agent's preceding turn, read directly from the session
    transcript at UserPromptSubmit time. Replaces the old Stop-hook handoff,
    which silently lost pre-text whenever the user interrupted a turn (no Stop
    event fires on cancel). Best-effort: returns "" on any problem."""
    if not transcript_path:
        return ""
    from pathlib import Path

    from . import claude_cli_get_recent_agent_messages as extractor

    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        return ""
    try:
        events = list(extractor.parse_events(transcript_file))
        return extractor.build_pre_text_for_incoming_user_prompt(
            events, incoming_prompt_text
        )
    except Exception:
        return ""


def _backfill_user_messages_sent_while_agent_was_working(
    project_id: str,
    session_id: str,
    transcript_path: "str | None",
    incoming_prompt_text: str,
) -> None:
    """Append raw-log entries for any user messages sent WHILE THE AGENT WAS WORKING
    that never got their own capture -- the messages between the PREVIOUS normal
    submission and this one (see the gap-anchored extractor). Appended in order, each
    with empty pre-text (there is no per-message prior-agent turn to attribute). No-op
    when the transcript is unavailable or nothing was missed."""
    if not transcript_path:
        return
    from pathlib import Path

    from . import claude_cli_get_recent_agent_messages as extractor

    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        return

    events = list(extractor.parse_events(transcript_file))
    missed_messages = extractor.find_user_messages_sent_while_agent_was_working(
        events, incoming_prompt_text
    )
    for missed_message_text in missed_messages:
        append_submission_to_raw_input_log(
            project_id=project_id,
            session_id=session_id,
            submission_text=missed_message_text,
            prior_assistant_output_text="",
        )


def _handle_user_prompt_submit_hook() -> int:
    try:
        hook_input = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        hook_input = {}
    session_id = (
        hook_input.get("session_id")
        or hook_input.get("sessionId")
        or "unknown-session"
    )
    submission_text = (
        hook_input.get("prompt")
        or hook_input.get("user_prompt")
        or hook_input.get("userPrompt")
        or ""
    )
    transcript_path = hook_input.get("transcript_path") or hook_input.get("transcriptPath")

    project_id = resolve_project_id_for_session(session_id)
    if project_id is None:
        print(json.dumps({}))
        return 0

    # Pre-text = the agent's preceding turn, read straight from the transcript
    # (text + tool results). Done here in UserPromptSubmit -- which fires on every
    # prompt -- so an interrupted/canceled turn (no Stop event) no longer drops it.
    prior_assistant_output_text = _extract_pre_text_from_transcript_for_prompt(
        transcript_path, submission_text
    )

    # LOOK-BEHIND: back-fill any user messages sent WHILE THE AGENT WAS WORKING
    # (promptSource=="queued") that were never captured -- the messages that arrived
    # between two normal submissions. They are appended BEFORE the current prompt so
    # they keep their chronological raw_input_ids. Best-effort: any failure here must
    # never block capturing the current prompt.
    try:
        _backfill_user_messages_sent_while_agent_was_working(
            project_id=project_id,
            session_id=session_id,
            transcript_path=transcript_path,
            incoming_prompt_text=submission_text,
        )
    except Exception:
        pass

    log_result = append_submission_to_raw_input_log(
        project_id=project_id,
        session_id=session_id,
        submission_text=submission_text,
        prior_assistant_output_text=prior_assistant_output_text,
    )
    additional_context = _build_per_turn_additional_context_line(
        project_id=project_id,
        raw_input_id=log_result["raw_input_id"],
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": additional_context,
    }}))
    return 0


# ----- Setup verbs -----

def _handle_add_session(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: source-of-truth add-session <project_id> <session_id> <conversation_path>", file=sys.stderr)
        return 2
    project_id, session_id, conversation_path = argv
    try:
        was_added = add_session_to_project(project_id, session_id, conversation_path)
    except SessionAlreadyInDifferentProjectError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("added" if was_added else "already_present")
    return 0


def _handle_init_project(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: source-of-truth init-project <project_id>", file=sys.stderr)
        return 2
    project_id = argv[0]
    ensure_root_directories_exist()
    save_requirements_tree_atomically(RequirementsTree.scaffolded_for_new_project(project_id))
    print(f"initialized project_id={project_id}")
    return 0


def _handle_init_and_register(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "Usage: source-of-truth init-and-register <session_id> <conversation_path>\n"
            "  project_id is set to <session_id> by convention.",
            file=sys.stderr,
        )
        return 2
    session_id, conversation_path = argv
    project_id = session_id
    from .install_health_check import run_install_health_check_quietly
    if run_install_health_check_quietly():
        print("Installation health check complete")
    ensure_root_directories_exist()
    try:
        was_added = add_session_to_project(project_id, session_id, conversation_path)
    except SessionAlreadyInDifferentProjectError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    save_requirements_tree_atomically(RequirementsTree.scaffolded_for_new_project(project_id))
    print(
        f"initialized project_id={project_id}; "
        f"session={'added' if was_added else 'already_present'}"
    )
    return 0


def _handle_set_mode(argv: list[str]) -> int:
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) != 1:
        print(
            f"Usage: source-of-truth set-mode <{'|'.join(ALL_VALID_REVIEWER_MODES)}>",
            file=sys.stderr,
        )
        return 2
    requested_mode = rest[0]
    if requested_mode not in ALL_VALID_REVIEWER_MODES:
        print(
            f"Invalid mode {requested_mode!r}. Valid: {', '.join(ALL_VALID_REVIEWER_MODES)}",
            file=sys.stderr,
        )
        return 2
    settings = load_project_settings(project_id)
    settings.reviewer_mode_override = requested_mode
    save_project_settings(settings)
    print(f"reviewer_mode_override set to '{requested_mode}'")
    return 0


# ----- Runtime verbs (agent-facing) -----

def _extract_named_flag_value_from_argv_or_none(
    argv: list[str], flag_name: str
) -> "str | None":
    """If `--flag value` appears in argv, return the value; else None."""
    for index, token in enumerate(argv):
        if token == flag_name and index + 1 < len(argv):
            return argv[index + 1]
    return None


def _build_combo_or_leaf_or_group_shortcut_payload(
    payload_args: list[str], project_id_for_combo_letter_lookup: "str | None"
) -> dict:
    """Convenience shortcut forms for one- or two-op change-sets.

    Listed in promotion order (combo first to encourage group creation):
    1. --add <raw_input_id> --parent <pid> --title "<leaf>" --new-group "<group>"
       (creates group under parent, then leaf under the new group; 2 ops)
    2. --add <raw_input_id> --parent <pid> --title "<leaf>"   (1 op)
    3. --add-group --parent <pid> --title "<group>"           (1 op)
    """
    has_add_flag = "--add" in payload_args
    has_add_group_flag = "--add-group" in payload_args
    if not (has_add_flag or has_add_group_flag):
        return {}

    explicit_parent_id_string = _extract_named_flag_value_from_argv_or_none(payload_args, "--parent")
    explicit_short_neutral_title = _extract_named_flag_value_from_argv_or_none(payload_args, "--title")
    new_group_short_neutral_title = _extract_named_flag_value_from_argv_or_none(payload_args, "--new-group")

    if has_add_flag:
        from .id_display import strip_raw_input_id_input_prefix
        try:
            add_flag_index = payload_args.index("--add")
            raw_input_id_string = payload_args[add_flag_index + 1]
            raw_input_id_int = int(strip_raw_input_id_input_prefix(raw_input_id_string))
        except (IndexError, ValueError) as exc:
            raise ValueError(
                f"--add requires an integer raw_input_id (optionally raw-prefixed) "
                f"immediately after it: {exc}"
            ) from exc
        if explicit_parent_id_string is None:
            raise ValueError("--add requires --parent <node_id_or_'0'>")
        if explicit_short_neutral_title is None:
            raise ValueError("--add requires --title \"<short_neutral_title>\"")

        # Combo form: also create a new group under the requested parent, and
        # attach the leaf under that new group. The new group's letter id is
        # predicted by reading the current tree's next_group_letter_index.
        if new_group_short_neutral_title is not None:
            from .requirements_tree_node_schema import letter_id_for_index
            from .requirements_tree_store import load_requirements_tree
            if project_id_for_combo_letter_lookup is None:
                # Test path with no project_id supplied: fall back to "a".
                predicted_new_group_letter_id = "a"
            else:
                tree = load_requirements_tree(project_id_for_combo_letter_lookup)
                predicted_new_group_letter_id = letter_id_for_index(tree.next_group_letter_index)
            return {
                "submitter_rationale": "combo: new group + leaf under it",
                "operations": [
                    {
                        "op": "add_group",
                        "parent_id": explicit_parent_id_string,
                        "short_neutral_title": new_group_short_neutral_title,
                    },
                    {
                        "op": "add",
                        "parent_id": predicted_new_group_letter_id,
                        "raw_input_reference": {"raw_input_id": raw_input_id_int},
                        "short_neutral_title": explicit_short_neutral_title,
                    },
                ],
            }

        # Leaf-only form.
        return {
            "submitter_rationale": f"add leaf under parent_id={explicit_parent_id_string}",
            "operations": [{
                "op": "add",
                "parent_id": explicit_parent_id_string,
                "raw_input_reference": {"raw_input_id": raw_input_id_int},
                "short_neutral_title": explicit_short_neutral_title,
            }],
        }

    # has_add_group_flag (no --add)
    if explicit_parent_id_string is None:
        raise ValueError("--add-group requires --parent <node_id_or_'0'>")
    if explicit_short_neutral_title is None:
        raise ValueError("--add-group requires --title \"<short_neutral_title>\"")
    return {
        "submitter_rationale": f"add group under parent_id={explicit_parent_id_string}",
        "operations": [{
            "op": "add_group",
            "parent_id": explicit_parent_id_string,
            "short_neutral_title": explicit_short_neutral_title,
        }],
    }


def _resolve_change_set_payload_from_argv_after_project_id(
    payload_args: list[str],
    stdin_text_supplier=None,
    project_id_for_combo_letter_lookup: "str | None" = None,
) -> dict:
    """Convenience-flag shortcuts (combo first) + JSON forms.

    Convenience-flag shortcuts (combo listed first to encourage tree organization):
      1. --add <rid> --parent <pid> --title "<leaf>" --new-group "<group title>"
      2. --add <rid> --parent <pid> --title "<leaf title>"
      3. --add-group --parent <pid> --title "<group title>"

    JSON forms:
      - @path/to/file.json                 -> read file
      - -                                  -> read JSON from stdin
      - <raw json>                         -> parse argv[0] as JSON
    """
    if "--add" in payload_args or "--add-group" in payload_args:
        return _build_combo_or_leaf_or_group_shortcut_payload(
            payload_args, project_id_for_combo_letter_lookup
        )
    if len(payload_args) == 1 and payload_args[0] == "-":
        if stdin_text_supplier is None:
            stdin_text = sys.stdin.read()
        else:
            stdin_text = stdin_text_supplier()
        return json.loads(stdin_text)
    if len(payload_args) == 1 and payload_args[0].startswith("@"):
        with open(payload_args[0][1:]) as f:
            return json.loads(f.read())
    if len(payload_args) == 1:
        return json.loads(payload_args[0])
    raise ValueError(
        "submit-change-set payload must be one of: "
        "convenience flags (--add / --add-group / --new-group) | "
        "@path/to/file.json | - (stdin) | <raw json>"
    )


def _handle_submit_change_set(argv: list[str]) -> int:
    project_id, payload_args, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(payload_args) < 1:
        print(
            "Usage: source-of-truth submit-change-set "
            "[--add <rid> --parent <pid> --title \"...\" --new-group \"...\" "
            "| --add <rid> --parent <pid> --title \"...\" "
            "| --add-group --parent <pid> --title \"...\" "
            "| @path/to/file.json | - (stdin) | <raw json>]",
            file=sys.stderr,
        )
        return 2
    try:
        change_set_dict = _resolve_change_set_payload_from_argv_after_project_id(
            payload_args, project_id_for_combo_letter_lookup=project_id,
        )
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Could not build change-set payload: {exc}", file=sys.stderr)
        return 2
    api = RequirementsTreeControlledApi(project_id, ClaudeCodeAdapter())
    result = api.submit_requirements_tree_change_set(change_set_dict)
    print(json.dumps({
        "approved": result.approved,
        "applied_operation_count": result.applied_operation_count,
        "assigned_node_ids": result.assigned_node_ids,
        "reviewer_message": result.reviewer_message,
        "message_for_raw_input_sender": result.message_for_raw_input_sender,
        "reviewer_thinking_log_path": result.reviewer_thinking_log_path,
    }, indent=2))
    return 0 if result.approved else 1


def _handle_show_tree(argv: list[str]) -> int:
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) > 1:
        print("Usage: source-of-truth show-tree [--show-all]", file=sys.stderr)
        return 2
    show_all_flag_present = len(rest) == 1 and rest[0] == "--show-all"
    if len(rest) == 1 and not show_all_flag_present:
        print(
            f"Unknown flag: {rest[0]!r}. Only --show-all is supported.",
            file=sys.stderr,
        )
        return 2
    tree = load_requirements_tree(project_id)
    from .compact_tree_renderer import render_tree_compact, render_tree_titles_only_indented
    if show_all_flag_present:
        print(render_tree_compact(project_id, tree))
    else:
        print(render_tree_titles_only_indented(project_id, tree))
    return 0


_NOT_IN_PROJECT_ERROR = "You must be part of a source-of-truth project to use this command."


def _resolve_project_and_remaining_args(
    args: list[str],
) -> "tuple[str | None, list[str], str | None]":
    """Resolve which project a runtime verb operates on, WITHOUT the agent ever
    passing a project id.

    Resolution order:
      1. an explicit, UNDOCUMENTED override (`--project <id>`, or a leading
         positional that names an existing project on disk) — for portability;
      2. otherwise the current session via CLAUDE_CODE_SESSION_ID.
    Returns (project_id, remaining_args, error_message). error_message is set
    (and project_id is None) when the session is not part of any project.
    """
    args = list(args)
    explicit_project_id: "str | None" = None

    if "--project" in args:
        flag_index = args.index("--project")
        if flag_index + 1 < len(args):
            explicit_project_id = args[flag_index + 1]
            del args[flag_index : flag_index + 2]

    # Only a BARE token (no path separator, not absolute) may be a positional
    # project-id override. A project id is a single directory name under
    # PROJECTS_PARENT_DIR. Without this guard, a path-like argument -- notably
    # add-path's absolute filesystem path -- would be misread as a project id:
    # project_directory_for('/abs/dir') collapses (via pathlib's `/`) to
    # '/abs/dir' itself, which often exists, so the real argument would be
    # silently consumed as the project override.
    if (
        explicit_project_id is None
        and args
        and not args[0].startswith("-")
        and not os.path.isabs(args[0])
        and "/" not in args[0]
        and os.sep not in args[0]
        and project_directory_for(args[0]).is_dir()
    ):
        explicit_project_id = args[0]
        args = args[1:]

    if explicit_project_id is not None:
        return explicit_project_id, args, None

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    project_id = resolve_project_id_for_session(session_id) if session_id else None
    if project_id is None:
        return None, args, _NOT_IN_PROJECT_ERROR
    return project_id, args, None


_PRETEXT_TOOL_REMINDER_LINE = (
    "[pretext] Nodes above show their agent pre-text line-numbered. To narrow one: "
    "`source-of-truth pretext <node_id> <start> <end>`  |  `--all` (whole)  |  `--none` (hide)."
)


def _attach_numbered_pre_text_to_node_payload(project_id: str, node_payload: dict) -> bool:
    """Enrich a read payload with the entry's line-numbered agent pre-text and the
    node's current selection. Returns True if the node is a quote reference."""
    node_dict = node_payload.get("node", {})
    reference = node_dict.get("raw_input_reference")
    if not reference:
        return False
    from .raw_input_log_reader import get_raw_log_entry_by_raw_input_id, RawLogEntryNotFoundError
    selection = reference.get("pre_text_line_range")
    node_payload["pre_text_selection"] = "all" if selection is None else selection
    try:
        entry = get_raw_log_entry_by_raw_input_id(project_id, reference["raw_input_id"])
    except (RawLogEntryNotFoundError, KeyError):
        node_payload["agent_pre_text_numbered"] = "(entry not found)"
        return True
    pre_text = entry.pre_submission_content
    if not pre_text:
        node_payload["agent_pre_text_numbered"] = "(no agent pre-text)"
    else:
        node_payload["agent_pre_text_numbered"] = "\n".join(
            f"{line_number}| {line_text}"
            for line_number, line_text in enumerate(pre_text.split("\n"), 1)
        )
    return True


def _handle_read(argv: list[str]) -> int:
    """Read one or more nodes by id; mixed quote-leaf ids (e.g. "12") and group letter ids (e.g. "a")."""
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) < 1:
        print("Usage: source-of-truth read <node_id> [<node_id> ...]", file=sys.stderr)
        return 2
    from .id_display import strip_node_id_input_prefix
    requested_node_ids = [strip_node_id_input_prefix(token) for token in rest]
    api = RequirementsTreeControlledApi(project_id, ClaudeCodeAdapter())
    payload_per_node: list[dict] = []
    any_id_failed = False
    any_quote_node_shown = False
    for requested_node_id_string in requested_node_ids:
        node_payload = api.get_node_by_id(requested_node_id_string, include_children=True)
        if node_payload is None:
            payload_per_node.append({
                "requested_node_id": requested_node_id_string,
                "error": f"node_id {requested_node_id_string!r} not found",
            })
            any_id_failed = True
        else:
            node_payload["requested_node_id"] = requested_node_id_string
            if _attach_numbered_pre_text_to_node_payload(project_id, node_payload):
                any_quote_node_shown = True
            payload_per_node.append(node_payload)
    print(json.dumps(payload_per_node, indent=2))
    if any_quote_node_shown:
        # To stderr so stdout stays pure JSON for parsers; the agent still sees it.
        print(_PRETEXT_TOOL_REMINDER_LINE, file=sys.stderr)
    return 1 if any_id_failed else 0


# Back-compat shim: keep _handle_get_node as an alias so any out-of-tree caller
# (or mid-flight test) doesn't import-fail. The dispatch table below maps both
# the old `get-node` verb and the new `read` verb to the same handler.
_handle_get_node = _handle_read


def _handle_search_nodes(argv: list[str]) -> int:
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) != 1:
        print("Usage: source-of-truth search-nodes <query>", file=sys.stderr)
        return 2
    query = rest[0]
    api = RequirementsTreeControlledApi(project_id, ClaudeCodeAdapter())
    print(json.dumps(api.search_requirements_nodes(query), indent=2))
    return 0


_LIST_RAW_PREVIEW_CHAR_LIMIT = 30


def _handle_list_raw(argv: list[str]) -> int:
    """List every raw-log entry as `raw-<id>: <first 30 chars>` so the agent can
    see what has been captured and decide which to file."""
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if rest:
        print("Usage: source-of-truth list-raw", file=sys.stderr)
        return 2
    from .id_display import format_raw_input_id_for_display
    from .raw_input_log_reader import list_all_raw_log_entries_for_project

    rows = list_all_raw_log_entries_for_project(project_id)
    if not rows:
        print("(no raw input log entries yet)")
        return 0
    for raw_input_id, _session_id, entry in rows:
        single_line = " ".join((entry.submission_text or "").split())
        preview = single_line[:_LIST_RAW_PREVIEW_CHAR_LIMIT]
        if len(single_line) > _LIST_RAW_PREVIEW_CHAR_LIMIT:
            preview += "…"
        print(f"{format_raw_input_id_for_display(raw_input_id)}: {preview}")
    return 0


def _handle_read_raw(argv: list[str]) -> int:
    """Print a single raw-log entry in full (submission + agent pre-text + timestamp)."""
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) != 1:
        print("Usage: source-of-truth read-raw <raw_input_id>", file=sys.stderr)
        return 2
    from .id_display import (
        format_raw_input_id_for_display,
        strip_raw_input_id_input_prefix,
    )
    from .raw_input_log_reader import (
        RawLogEntryNotFoundError,
        get_raw_log_entry_by_raw_input_id,
    )

    try:
        raw_input_id = int(strip_raw_input_id_input_prefix(rest[0]))
    except (TypeError, ValueError):
        print(f"invalid raw input id: {rest[0]!r}", file=sys.stderr)
        return 2
    try:
        entry = get_raw_log_entry_by_raw_input_id(project_id, raw_input_id)
    except RawLogEntryNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "raw_input_id": format_raw_input_id_for_display(raw_input_id),
        "timestamp_iso": entry.timestamp_iso,
        "submission_text": entry.submission_text,
        "pre_submission_content": entry.pre_submission_content,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _handle_flush_deferred(argv: list[str]) -> int:
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if rest:
        print("Usage: source-of-truth flush-deferred", file=sys.stderr)
        return 2
    api = RequirementsTreeControlledApi(project_id, ClaudeCodeAdapter())
    result = api.flush_deferred_change_sets_for_review()
    print(json.dumps({
        "approved": result.approved,
        "applied_operation_count": result.applied_operation_count,
        "reviewer_message": result.reviewer_message,
        "message_for_raw_input_sender": result.message_for_raw_input_sender,
    }, indent=2))
    return 0 if result.approved else 1


def _handle_add_path(argv: list[str]) -> int:
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) != 1:
        print("Usage: source-of-truth add-path <filesystem_path>", file=sys.stderr)
        return 2
    filesystem_path = rest[0]
    api = RequirementsTreeControlledApi(project_id, ClaudeCodeAdapter())
    try:
        was_added = api.add_project_path(filesystem_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("added" if was_added else "already_present")
    return 0


def _handle_rename(argv: list[str]) -> int:
    """Set a node's title; triggers a backgrounded title review.

    Usage: source-of-truth rename <node_id> "<new title>"
    Accepts an nd-prefixed or bare node id.
    """
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if len(rest) != 2:
        print('Usage: source-of-truth rename <node_id> "<new title>"', file=sys.stderr)
        return 2
    node_id, new_title = rest
    api = RequirementsTreeControlledApi(project_id, ClaudeCodeAdapter())
    if not api.rename_node_title(node_id, new_title):
        print(f"node {node_id!r} not found", file=sys.stderr)
        return 1
    print(f"renamed {node_id} -> {new_title!r}; title review queued in background")
    return 0


def _handle_show_top_level(argv: list[str]) -> int:
    project_id, rest, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    if rest:
        print("Usage: source-of-truth show-top-level", file=sys.stderr)
        return 2
    print(build_top_level_injection_text_for_project(project_id))
    return 0


def _handle_pretext(argv: list[str]) -> int:
    """Set how much of a node's agent pre-text is cited.

    Usage: source-of-truth pretext <node_id> <start> <end> | --all | --none
    Project is resolved from the current session (CLAUDE_CODE_SESSION_ID); an
    optional `--project <id>` override exists for portability (not shown in help).
    """
    project_id, tokens, error_message = _resolve_project_and_remaining_args(argv)
    if error_message:
        print(error_message, file=sys.stderr)
        return 1

    usage = "Usage: source-of-truth pretext <node_id> <start> <end> | --all | --none"
    if len(tokens) < 2:
        print(usage, file=sys.stderr)
        return 2
    from .id_display import strip_node_id_input_prefix
    node_id = strip_node_id_input_prefix(tokens[0])
    selection_tokens = tokens[1:]
    if selection_tokens == ["--all"]:
        new_selection = None            # whole pre-text (clear the narrowing)
    elif selection_tokens == ["--none"]:
        new_selection = "none"          # exclude pre-text
    elif (
        len(selection_tokens) == 2
        and selection_tokens[0].lstrip("-").isdigit()
        and selection_tokens[1].lstrip("-").isdigit()
    ):
        new_selection = [int(selection_tokens[0]), int(selection_tokens[1])]
    else:
        print(usage, file=sys.stderr)
        return 2

    tree = load_requirements_tree(project_id)
    node = tree.nodes_by_id.get(str(node_id))
    if node is None or node.raw_input_reference is None:
        print(f"node {node_id!r} not found or is not a quote-reference node", file=sys.stderr)
        return 1

    if isinstance(new_selection, list):
        from .raw_input_log_reader import (
            RawLogEntryNotFoundError,
            get_raw_log_entry_by_raw_input_id,
        )
        try:
            entry = get_raw_log_entry_by_raw_input_id(
                project_id, node.raw_input_reference.raw_input_id
            )
        except RawLogEntryNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        pre_text_line_count = (
            len(entry.pre_submission_content.split("\n")) if entry.pre_submission_content else 0
        )
        start_line_number, end_line_number = new_selection
        if pre_text_line_count == 0:
            print("this entry has no agent pre-text to slice", file=sys.stderr)
            return 1
        if start_line_number < 1 or end_line_number > pre_text_line_count or start_line_number > end_line_number:
            print(
                f"line range {new_selection} out of bounds (pre-text has "
                f"{pre_text_line_count} lines)",
                file=sys.stderr,
            )
            return 1

    node.raw_input_reference.pre_text_line_range = new_selection
    save_requirements_tree_atomically(tree)
    shown = (
        "whole pre-text"
        if new_selection is None
        else ("excluded" if new_selection == "none" else f"lines {new_selection[0]}-{new_selection[1]}")
    )
    print(f"node {node_id}: agent pre-text now {shown}")
    return 0


_VERB_DISPATCH_TABLE = {
    # hook
    "user-prompt-submit-hook": lambda argv: _handle_user_prompt_submit_hook(),
    # setup
    "init-project": _handle_init_project,
    "init-and-register": _handle_init_and_register,
    "add-session": _handle_add_session,
    "set-mode": _handle_set_mode,
    # runtime (agent-facing)
    "submit-change-set": _handle_submit_change_set,
    "show-tree": _handle_show_tree,
    "read": _handle_read,
    "get-node": _handle_read,  # legacy alias; remove in a future refactor
    "search-nodes": _handle_search_nodes,
    "list-raw": _handle_list_raw,
    "read-raw": _handle_read_raw,
    "pretext": _handle_pretext,
    "flush-deferred": _handle_flush_deferred,
    "add-path": _handle_add_path,
    "rename": _handle_rename,
    "show-top-level": _handle_show_top_level,
}


_VERB_ONE_LINER_DESCRIPTIONS = {
    "user-prompt-submit-hook": "Internal: handle a UserPromptSubmit hook event (not for direct use).",
    "init-project": "Create a new project tree (no session enrollment).",
    "init-and-register": "Create a new project AND enroll the calling session as a member.",
    "add-session": "Enroll an additional Claude Code session into an existing project.",
    "set-mode": "Set reviewer mode for a session: live | none | deferred.",
    "submit-change-set": "Submit one or more ops (add / add_group / reparent / etc.) to mutate the tree.",
    "show-tree": "Print the project's requirement tree (titles by default; --show-all inlines quotes).",
    "read": "Read one or more nodes by id (mixed leaf + group ok).",
    "get-node": "Alias for `read` (kept for backwards compatibility).",
    "search-nodes": "Search node titles + raw quotes by keyword.",
    "list-raw": "List every raw-log entry as raw-<id>: <first 30 chars> (to see what was captured).",
    "read-raw": "Print one raw-log entry in full by id: read-raw <raw_input_id>.",
    "pretext": "Set how much of a node's agent pre-text is cited: <node_id> <start> <end> | --all | --none.",
    "flush-deferred": "Apply queued submits in deferred mode (no-op otherwise).",
    "add-path": "Pin a filesystem path on a project's project-paths node.",
    "rename": "Set a node's title (triggers a backgrounded title review).",
    "show-top-level": "Print only the top-level group/leaf summary for a project.",
}


_TOP_LEVEL_HELP_TOKENS = {"--help", "-h", "help", "-?", "/?"}


def _print_top_level_help() -> None:
    """Write usage + per-verb blurbs to stdout."""
    print("Usage: source-of-truth <verb> [args...]")
    print()
    print("Verbs:")
    longest_verb_name_length = max(len(verb_name) for verb_name in _VERB_DISPATCH_TABLE)
    for verb_name in _VERB_DISPATCH_TABLE:
        blurb = _VERB_ONE_LINER_DESCRIPTIONS.get(verb_name, "")
        print(f"  {verb_name.ljust(longest_verb_name_length)}  {blurb}")
    print()
    print("Top-level help: source-of-truth --help | -h | help")
    print("Per-verb args are not yet self-documenting; see README.md / SKILL.md for details.")


def _main() -> int:
    if len(sys.argv) < 2:
        # Zero-arg invocation: keep prior behavior (compact stderr banner, exit 2).
        # The proper way to learn the CLI is `source-of-truth --help`.
        print(
            f"Usage: source-of-truth <verb> [...]\nVerbs: {', '.join(_VERB_DISPATCH_TABLE)}\n"
            f"For descriptions, run: source-of-truth --help",
            file=sys.stderr,
        )
        return 2
    verb = sys.argv[1]
    if verb in _TOP_LEVEL_HELP_TOKENS:
        _print_top_level_help()
        return 0
    handler = _VERB_DISPATCH_TABLE.get(verb)
    if handler is None:
        print(
            f"Unknown verb: {verb}\nRun `source-of-truth --help` for the verb list.",
            file=sys.stderr,
        )
        return 2
    return handler(sys.argv[2:])


if __name__ == "__main__":
    sys.exit(_main())
