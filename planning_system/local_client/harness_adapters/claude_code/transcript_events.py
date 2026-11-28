"""transcript_events: pure functions over parsed Claude Code transcript events (dicts from the JSONL
transcript). No I/O: parse lines, find the events since the last genuine user prompt, extract text and
tool-result blocks, and build the pre-text for an incoming prompt. Reusable by any Claude Code tool and
testable on strings. The hook script `claude_cli_get_recent_agent_messages.py` is the thin I/O entry."""
from __future__ import annotations

import json
from typing import Iterable, Iterator


def parse_event_lines(lines: Iterable[str]) -> Iterator[dict]:
    """Yield parsed events from JSONL lines. Tolerates malformed lines."""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            # Skip malformed lines (e.g., partial trailing writes).
            continue


# When the user interrupts/cancels a turn, Claude Code writes a SYNTHETIC
# type=="user" event into the transcript whose text is one of these markers
# (e.g. "[Request interrupted by user]" or "[Request interrupted by user for
# tool use]"). It is NOT a genuine prompt: it sits between the agent's partial
# output and the user's next real prompt. If it were treated as the "last user
# prompt" boundary, the preceding agent output (which is BEFORE the marker) would
# be excluded and the pre-text would come back empty -- the exact interrupted-turn
# bug. Matched by prefix so both the plain and "for tool use" variants are caught.
_INTERRUPT_MARKER_TEXT_PREFIX: str = "[Request interrupted by user"


def _is_interrupt_marker_text(text: str) -> bool:
    """True if this text is a Claude Code interrupt/cancel marker pseudo-prompt."""
    return text.strip().startswith(_INTERRUPT_MARKER_TEXT_PREFIX)


def _is_genuine_user_prompt(event: dict) -> bool:
    """True only for a real user prompt, NOT a tool result and NOT an
    interrupt/cancel marker.

    Claude Code records tool results as type=="user" events whose
    message.content is a list containing tool_result blocks. A genuine user
    prompt has message.content as a plain string (or a list with no
    tool_result blocks, e.g. text+attachment prompts). Tool results must not
    count as the "last user message" boundary, otherwise assistant text
    emitted during a tool-use loop (the common case) is missed and the
    extractor returns empty.

    Interrupt/cancel markers (also type=="user", string content) are likewise
    excluded so a canceled turn's preceding agent output is still captured.
    """
    if event.get("type") != "user":
        return False
    content = event.get("message", {}).get("content")
    if isinstance(content, str):
        return not _is_interrupt_marker_text(content)
    if isinstance(content, list):
        if any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        ):
            return False
        # text+attachment prompt: still exclude if its text is just a marker.
        return not _is_interrupt_marker_text(_genuine_user_prompt_text(event))
    return False


def find_assistant_events_since_last_user(events: list[dict]) -> list[dict]:
    """Return all assistant events after the most recent genuine user prompt.

    Tool-result events (also type=="user") are skipped when locating the
    boundary so that all assistant text across a within-turn tool-use loop
    is captured, per this module's stated contract.
    """
    last_user_index = -1
    for i, event in enumerate(events):
        if _is_genuine_user_prompt(event):
            last_user_index = i

    return [
        event
        for event in events[last_user_index + 1 :]
        if event.get("type") == "assistant"
    ]


def extract_text_blocks(assistant_event: dict, include_tool_calls: bool) -> list[str]:
    """Extract text content from an assistant event.

    Returns a list of strings, one per content block. Text blocks become
    their text; tool_use blocks become a summary line (only when
    include_tool_calls is True).
    """
    message = assistant_event.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return []

    pieces: list[str] = []
    for block in content:
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text", "")
            if text:
                pieces.append(text)
        elif block_type == "tool_use" and include_tool_calls:
            tool_name = block.get("name", "<unknown>")
            tool_input = block.get("input", {})
            try:
                input_repr = json.dumps(tool_input, separators=(",", ":"))
            except (TypeError, ValueError):
                input_repr = str(tool_input)
            pieces.append(f"[tool: {tool_name}] {input_repr}")
        # Other block types (tool_result, thinking, etc.) ignored.
    return pieces


def extract_tool_result_blocks(user_event: dict) -> list[str]:
    """Extract tool_result OUTPUT text from a user event.

    Claude Code stores tool results as type=='user' events whose
    message.content is a list of tool_result blocks. Each tool_result block's
    own 'content' is usually a plain string, but may be a list of text blocks.
    Returns one '[tool_result] <text>' string per non-empty result.
    """
    message = user_event.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return []

    pieces: list[str] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        result_content = block.get("content", "")
        if isinstance(result_content, str):
            text = result_content
        elif isinstance(result_content, list):
            parts = []
            for inner_block in result_content:
                if isinstance(inner_block, dict) and inner_block.get("type") == "text":
                    parts.append(inner_block.get("text", ""))
                elif isinstance(inner_block, str):
                    parts.append(inner_block)
            text = "\n".join(part for part in parts if part)
        else:
            text = ""
        if text:
            pieces.append(f"[tool_result] {text}")
    return pieces


def find_events_since_last_user_prompt(events: list[dict]) -> list[dict]:
    """Return ALL events (any type, in chronological order) after the most
    recent genuine user prompt.

    Unlike find_assistant_events_since_last_user, this keeps the interleaved
    tool-result (type=='user') events so a consumer can include tool output.
    Tool-result events are not treated as the boundary.
    """
    last_user_index = -1
    for i, event in enumerate(events):
        if _is_genuine_user_prompt(event):
            last_user_index = i
    return events[last_user_index + 1 :]


def build_recent_agent_text_from_relevant_events(
    relevant_events: list[dict],
    include_tool_calls: bool,
    include_tool_results: bool,
    separator: str,
    max_chars: "int | None",
) -> str:
    """Assemble the plain-text capture string: assistant text (and optionally
    tool_use call summaries and/or tool_result output) since the last user
    prompt, in chronological order.

    When max_chars is set, only the LAST max_chars characters are kept -- the
    'most recent, from the bottom' capture window. Returns "" when empty.
    """
    messages: list[str] = []
    for event in relevant_events:
        event_type = event.get("type")
        if event_type == "assistant":
            pieces = extract_text_blocks(event, include_tool_calls)
            if pieces:
                messages.append("\n".join(pieces))
        elif event_type == "user" and include_tool_results:
            pieces = extract_tool_result_blocks(event)
            if pieces:
                messages.append("\n".join(pieces))

    if not messages:
        return ""
    output_text = separator.join(messages)
    if max_chars is not None and max_chars >= 0:
        output_text = output_text[-max_chars:]
    return output_text


def _genuine_user_prompt_text(event: dict) -> str:
    """The plain text of a genuine user-prompt event (content is a string, or a
    list of text blocks). Used to tell whether an incoming prompt has already
    been appended to the transcript."""
    content = event.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(part for part in parts if part)
    return ""


# A message the user types WHILE THE AGENT IS WORKING is recorded in the transcript
# as a ``queued_command`` ATTACHMENT event (NOT a type=="user" prompt event), because
# it does not fire its own UserPromptSubmit hook. Its human-typed variety carries
# commandMode=="prompt" and origin.kind=="human"; task-notifications reuse the same
# attachment shape but with commandMode=="task-notification" and are excluded.
def _is_human_queued_command_attachment(event: dict) -> bool:
    if event.get("type") != "attachment":
        return False
    attachment = event.get("attachment") or {}
    if attachment.get("type") != "queued_command":
        return False
    if attachment.get("commandMode") != "prompt":
        return False
    return (attachment.get("origin") or {}).get("kind") == "human"


def _queued_command_attachment_text(event: dict) -> str:
    return ((event.get("attachment") or {}).get("prompt")) or ""


def find_user_messages_sent_while_agent_was_working(
    events: list[dict],
    incoming_prompt_text: str,
) -> list[str]:
    """GAP-ANCHORED look-behind: return the texts of human messages the user sent
    WHILE THE AGENT WAS WORKING that were never captured -- the messages between the
    PREVIOUS normal submission and this one.

    The reliable fact (the user's stated approach): a message sent while the agent is
    working does NOT fire its own UserPromptSubmit hook, so it is never logged; but the
    hook DOES fire on every normal submission (that is what runs this code). So we
    anchor on the previous normal submission's position in the transcript (the previous
    genuine user prompt) and collect the human ``queued_command`` attachments that fall
    AFTER it and before the incoming prompt. Scoping to this single gap means we never
    rescan old history (including a forked transcript's pre-fork messages), so there is
    no cross-session duplication -- this is deliberately NOT a content-dedup approach.

    The incoming prompt itself is excluded (the caller logs it through the normal path).
    """
    incoming_stripped = (incoming_prompt_text or "").strip()
    genuine_prompt_indices = [
        index for index, event in enumerate(events) if _is_genuine_user_prompt(event)
    ]

    # Anchor = the PREVIOUS normal submission's position; window ends at the incoming.
    if (
        genuine_prompt_indices
        and _genuine_user_prompt_text(events[genuine_prompt_indices[-1]]).strip()
        == incoming_stripped
    ):
        # The incoming prompt is already appended as the last genuine prompt: the gap
        # is between the one-before-last genuine prompt and it.
        anchor_index = (
            genuine_prompt_indices[-2] if len(genuine_prompt_indices) >= 2 else -1
        )
        window_end_index = genuine_prompt_indices[-1]
    else:
        # The incoming prompt is not yet appended: the gap runs from the last genuine
        # prompt to the end of the transcript.
        anchor_index = genuine_prompt_indices[-1] if genuine_prompt_indices else -1
        window_end_index = len(events)

    messages_to_backfill: list[str] = []
    for event in events[anchor_index + 1 : window_end_index]:
        if not _is_human_queued_command_attachment(event):
            continue
        queued_text = _queued_command_attachment_text(event)
        # Never back-fill the incoming prompt itself (it may be a queued message being
        # consumed as THIS submission; the normal path logs it).
        if queued_text.strip() and queued_text.strip() != incoming_stripped:
            messages_to_backfill.append(queued_text)
    return messages_to_backfill


def build_pre_text_for_incoming_user_prompt(
    events: list[dict],
    incoming_prompt_text: str,
    include_tool_results: bool = True,
    separator: str = "\n\n",
    max_chars: "int | None" = None,
) -> str:
    """Return the agent's output for the turn IMMEDIATELY PRECEDING an incoming
    user prompt, read straight from the transcript at UserPromptSubmit time.

    This replaces the old Stop-hook handoff: the Stop event never fires when the
    user interrupts/cancels a turn, so a Stop-based capture silently dropped the
    pre-text for those turns. UserPromptSubmit fires on EVERY prompt, so reading
    the transcript here captures the preceding turn (including its partial output
    when interrupted) every time.

    Robust to hook timing -- i.e. whether the incoming prompt has already been
    appended to the transcript when this runs:
      * if the LAST genuine user prompt equals the incoming prompt, the preceding
        turn is the span BETWEEN the two most recent genuine user prompts;
      * otherwise (incoming prompt not yet written) it is everything AFTER the
        last genuine user prompt.
    Returns "" when there is no preceding agent turn (e.g. the first prompt)."""
    genuine_indices = [i for i, event in enumerate(events) if _is_genuine_user_prompt(event)]
    if not genuine_indices:
        return ""
    last_index = genuine_indices[-1]
    incoming_already_appended = (
        _genuine_user_prompt_text(events[last_index]).strip()
        == (incoming_prompt_text or "").strip()
    )
    if incoming_already_appended:
        if len(genuine_indices) < 2:
            return ""  # the incoming prompt is the very first; no preceding turn
        preceding_turn_events = events[genuine_indices[-2] + 1 : last_index]
    else:
        preceding_turn_events = events[last_index + 1 :]
    return build_recent_agent_text_from_relevant_events(
        preceding_turn_events,
        include_tool_calls=False,   # the CALL is noise; the RESULT is the signal
        include_tool_results=include_tool_results,
        separator=separator,
        max_chars=max_chars,
    )
