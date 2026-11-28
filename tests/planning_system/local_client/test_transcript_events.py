"""transcript_events: pure transcript functions, tested on strings (no files, no hook payload)."""
import json

from planning_system.local_client.harness_adapters.claude_code.transcript_events import (
    build_pre_text_for_incoming_user_prompt, find_events_since_last_user_prompt, parse_event_lines)


def _user(text):
    return {"type": "user", "message": {"content": text}}


def _assistant(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def test_parse_event_lines_skips_blank_and_malformed_lines():
    lines = [json.dumps(_user("hi")), "", "{not json", json.dumps(_assistant("yo"))]
    assert list(parse_event_lines(lines)) == [_user("hi"), _assistant("yo")]


def test_events_since_last_user_prompt():
    events = [_user("one"), _assistant("a"), _user("two"), _assistant("b")]
    assert find_events_since_last_user_prompt(events) == [_assistant("b")]


def test_pre_text_is_the_turn_before_the_incoming_prompt():
    events = [_user("one"), _assistant("answer one"), _user("two")]
    assert build_pre_text_for_incoming_user_prompt(events, "two") == "answer one"
    assert build_pre_text_for_incoming_user_prompt(events[:2], "two") == "answer one"
    assert build_pre_text_for_incoming_user_prompt([_user("one")], "one") == ""
