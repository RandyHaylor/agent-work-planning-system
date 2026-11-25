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

Self-gating: emits {} for a non-AskUserQuestion tool, a payload without a session id,
or when there are no answers (dismissed/rejected prompt). Planning system: entries go to
the local client cache (quote_capture), never to the server.
"""
from __future__ import annotations

import json
import sys

from planning_system.local_client.client_paths import ClientPaths
from planning_system.local_client.quote_capture.exchange_capture import ExchangeCaptureService
from planning_system.local_client.quote_capture.jsonl_exchange_cache import JsonlExchangeCache
from planning_system.local_client.quote_capture.ports import LocalExchangeCachePort
from planning_system.local_client.quote_capture.production_ports import SystemClock

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


def handle_post_tool_use(hook_input: dict, cache: LocalExchangeCachePort) -> dict:
    """Planning system port: each answered question becomes one exchange in the LOCAL cache (question as
    pre-text, answer as the user message). SoT's project gating is dropped; nothing is sent to the server."""
    if hook_input.get("tool_name") != ASKUSERQUESTION_TOOL_NAME:
        return {}
    session_id = hook_input.get("session_id") or hook_input.get("sessionId")
    if not session_id:
        return {}
    answers, questions = _extract_answers_and_questions(hook_input)
    if not answers:
        # Dismissed / rejected / no selection -> nothing to capture.
        return {}

    capture = ExchangeCaptureService(None, cache, SystemClock())
    logged_entries = []
    for question_text in _ordered_question_texts(answers, questions):
        answer_text = answers.get(question_text, "")
        local_id = capture.capture_question_answer(session_id, question_text, answer_text)
        logged_entries.append((local_id, question_text, answer_text))

    context_lines = [
        f"planning: saved {len(logged_entries)} AskUserQuestion answer(s) locally. Each is an explicit user "
        f"decision; to quote one, run `planning cite-exchange <id>` and cite the returned reference:"
    ]
    for local_id, question_text, answer_text in logged_entries:
        context_lines.append(f"  exchange {local_id}: Q={question_text!r} A={answer_text!r}")
    return {"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "\n".join(context_lines),
    }}


def _main(stdin=None, stdout=None, cache: "LocalExchangeCachePort | None" = None) -> int:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    try:
        raw_stdin_text = stdin.read()
        hook_input = json.loads(raw_stdin_text) if raw_stdin_text else {}
        output = handle_post_tool_use(
            hook_input, cache or JsonlExchangeCache(ClientPaths.from_environment().exchange_cache_file))
    except Exception:
        output = {}
    print(json.dumps(output), file=stdout)
    return 0


main = _main

if __name__ == "__main__":
    sys.exit(_main())
