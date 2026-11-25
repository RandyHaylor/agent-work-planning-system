import pytest
from fastReader.preview import extract_preview

def test_extract_preview_basic():
    """T10: extract_preview(lines, line_number, char_index, length=30) returns N chars from correct position."""
    lines = ["Line 1", "Line 2: This is a longer line for testing", "Line 3"]
    # line_number is 1-indexed. Line 2 is index 1.
    preview = extract_preview(lines, 2, 8, length=10)
    assert preview == "This is a "

def test_extract_preview_short_content():
    """T11: extract_preview with shorter remaining content returns what's available (no error)."""
    lines = ["Short"]
    preview = extract_preview(lines, 1, 0, length=30)
    assert preview == "Short"

def test_extract_preview_beyond_document():
    """T12: extract_preview with line_number beyond document length returns ""."""
    lines = ["Line 1"]
    preview = extract_preview(lines, 5, 0)
    assert preview == ""

def test_extract_preview_respects_char_index():
    """T13: extract_preview respects char_index (skips leading whitespace)."""
    lines = ["  Indented Title"]
    # char_index=2 is 'I'
    preview = extract_preview(lines, 1, 2, length=8)
    assert preview == "Indented"

def test_extract_preview_default_length():
    """T14: extract_preview default length is 30."""
    lines = ["This is a very long line that should be truncated by the default length of thirty characters."]
    preview = extract_preview(lines, 1, 0)
    assert len(preview) == 30
    assert preview == "This is a very long line that "
