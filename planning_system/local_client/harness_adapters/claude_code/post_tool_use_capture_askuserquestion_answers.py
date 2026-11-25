"""PostToolUse hook: capture answered AskUserQuestion selections into the raw input log.

AskUserQuestion answers never fire UserPromptSubmit (they return as a tool result),
so without this hook the user's multiple-choice decisions are never logged and can't
be cited as source-of-truth requirements. PostToolUse for the AskUserQuestion tool
fires only AFTER the user submits answers (a dismissed/rejected prompt does not fire
it), so its presence with a populated answers map means "the user answered".

One raw_input_log entry is appended PER question (the answer is submission_text; the
question text is pre_submission_content), so each decision gets its own raw_input_id
the agent can cite in an add op. The new ids are handed back to the agent via
hookSpecificOutput.additionalContext.

Verified payload shape (PostToolUse, tool_name == "AskUserQuestion"):
  tool_input.questions[]      -> {question, header, options[], multiSelect}
  tool_input.answers          -> {question_text: answer_string}
                                  single-select -> chosen label
                                  multiSelect   -> labels joined with ", "
                                  "Other"       -> raw free-text verbatim
  (tool_response echoes the same questions + answers.)

Self-gating: emits {} for any session not registered to a SoT project, for a non-
AskUserQuestion tool, or when there are no answers (dismissed/rejected prompt).
"""
from __future__ import annotations

import json
import sys

ASKUSERQUESTION_TOOL_NAME = "AskUserQuestion"


def _extract_answers_and_questions(hook_input: dict) -> "tuple[dict, list]":
    """Return (answers_map, questions_list). answers maps question text -> answer
    string. Reads tool_input first, falling back to the tool_response echo."""
    tool_input = hook_input.get("tool_input") or {}
    tool_response = hook_input.get("tool_response") or {}

    answers = tool_input.get("answers")
    if not isinstance(answers, dict) and isinstance(tool_response, dict):
        answers = tool_response.get("answers")
    questions = tool_input.get("questions")
    if not isinstance(questions, list) and isinstance(tool_response, dict):
        questions = tool_response.get("questions")

    return (
        answers if isinstance(answers, dict) else {},
        questions if isinstance(questions, list) else [],
    )


def _ordered_question_texts(answers: dict, questions: list) -> list:
    """Question texts in the order the user saw them (questions list), with any
    answer keys not present in the questions list appended afterward."""
    ordered = [
        q.get("question")
        for q in questions
        if isinstance(q, dict) and q.get("question") in answers
    ]
    for q_text in answers:
        if q_text not in ordered:
            ordered.append(q_text)
    return ordered


def _main() -> int:
    try:
        raw_stdin_text = sys.stdin.read()
    except Exception:
        print(json.dumps({}))
        return 0
    try:
        hook_input = json.loads(raw_stdin_text) if raw_stdin_text else {}
    except json.JSONDecodeError:
        hook_input = {}

    if hook_input.get("tool_name") != ASKUSERQUESTION_TOOL_NAME:
        print(json.dumps({}))
        return 0
    session_id = hook_input.get("session_id") or hook_input.get("sessionId")
    if not session_id:
        print(json.dumps({}))
        return 0

    try:
        from .project_identifier_resolver import resolve_project_id_for_session
        from .raw_input_log_writer import append_submission_to_raw_input_log
    except Exception:
        print(json.dumps({}))
        return 0

    project_id = resolve_project_id_for_session(session_id)
    if project_id is None:
        print(json.dumps({}))
        return 0

    answers, questions = _extract_answers_and_questions(hook_input)
    if not answers:
        # Dismissed / rejected / no selection -> nothing to capture.
        print(json.dumps({}))
        return 0

    logged_entries = []
    for question_text in _ordered_question_texts(answers, questions):
        answer_text = answers.get(question_text, "")
        result = append_submission_to_raw_input_log(
            project_id=project_id,
            session_id=session_id,
            submission_text=answer_text,
            prior_assistant_output_text=f"[AskUserQuestion] {question_text}",
        )
        logged_entries.append((result["raw_input_id"], question_text, answer_text))

    context_lines = [
        f"source-of-truth: captured {len(logged_entries)} AskUserQuestion answer(s) "
        f"as raw_input_id(s). Each is an explicit user decision -- file it under "
        f"pending-instructions (or the fitting group) via "
        f"submit-change-set --add <raw_input_id> --parent <parent> --title \"<topic>\":"
    ]
    for raw_input_id, question_text, answer_text in logged_entries:
        context_lines.append(
            f"  raw_input_id {raw_input_id}: Q={question_text!r} A={answer_text!r}"
        )

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "\n".join(context_lines),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
