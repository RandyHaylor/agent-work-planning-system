"""Spec test 12: real-library smoke tests, one fixture per format. Real only."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from planning_system.document_extraction import SourceDocument, build_document_extractor

FIXTURES = Path(__file__).parents[1] / "fixtures"

CASES = [
    ("article.html", "text/html", "Fixture article"),
    ("tiny.pdf", "application/pdf", "Fixture PDF text"),
    ("report.docx", None, "First paragraph of the fixture Word document."),
    ("sample.json", "application/json", '"b": 1'),
    ("sample.jsonl", None, '"id": 3'),
    ("notes.txt", "text/plain", "Plain notes."),
]


@pytest.mark.parametrize("file_name,header,expected", CASES)
def test_12_real_libraries_extract_fixture(file_name, header, expected):
    document = SourceDocument(raw_bytes=(FIXTURES / file_name).read_bytes(), locator=file_name,
                              origin_kind="upload", fetched_at=datetime.now(timezone.utc),
                              content_type_header=header, file_name=file_name, metadata={})
    result = build_document_extractor({}).extract(document)
    assert expected in result.text
