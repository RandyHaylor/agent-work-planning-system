"""Cover the balanced-brace verdict JSON extractor: handles prose around the
JSON, embedded example braces, escaped quotes, and markdown fences."""
from __future__ import annotations

import json

import pytest

from source_of_truth.requirements_modification_reviewer import (
    _extract_verdict_json_from_response,
)


def test_extracts_clean_json_object_with_no_surrounding_text():
    text = '{"ops": [{"index": 0, "approved": true, "reason": "ok"}], "message": "hi"}'
    parsed = _extract_verdict_json_from_response(text)
    assert parsed["message"] == "hi"
    assert parsed["ops"][0]["approved"] is True


def test_extracts_json_when_wrapped_in_markdown_fence():
    text = '```json\n{"ops": [{"index": 0, "approved": false, "reason": "no"}], "message": "x"}\n```'
    parsed = _extract_verdict_json_from_response(text)
    assert parsed["ops"][0]["approved"] is False


def test_picks_real_verdict_when_an_earlier_example_object_appears_in_prose():
    text = (
        "Sure, the schema looks like {\"ops\": [{\"index\": 0, \"approved\": true}]} "
        "in the docs. My actual verdict for this batch is below.\n"
        '{"ops": [{"index": 0, "approved": false, "reason": "real verdict"}], "message": "real"}'
    )
    parsed = _extract_verdict_json_from_response(text)
    assert parsed["message"] == "real"
    assert parsed["ops"][0]["reason"] == "real verdict"


def test_handles_escaped_quotes_inside_reason_field():
    text = r'{"ops": [{"index": 0, "approved": false, "reason": "user said \"no\" so reject"}], "message": "ok"}'
    parsed = _extract_verdict_json_from_response(text)
    assert parsed["ops"][0]["reason"] == 'user said "no" so reject'


def test_raises_when_no_json_object_present():
    with pytest.raises(ValueError):
        _extract_verdict_json_from_response("no json at all in here")


def test_falls_back_to_any_dict_if_no_object_with_ops_key_present():
    """Surface a useful error path: at least return something parseable."""
    text = '{"some_other_key": 42}'
    parsed = _extract_verdict_json_from_response(text)
    assert parsed == {"some_other_key": 42}
