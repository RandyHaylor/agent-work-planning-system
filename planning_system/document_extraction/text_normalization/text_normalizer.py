"""Dispatch by TextKind."""
from __future__ import annotations

from planning_system.document_extraction.extraction_interface import TextNormalizer
from planning_system.document_extraction.extraction_types import TextKind
from planning_system.document_extraction.text_normalization.json_formatter import format_json
from planning_system.document_extraction.text_normalization.jsonl_formatter import format_jsonl
from planning_system.document_extraction.text_normalization.line_endings import normalize_line_endings
from planning_system.document_extraction.text_normalization.prose_wrapper import ProseWrapper


class KindTextNormalizer(TextNormalizer):
    def __init__(self, wrap_width: int = 100, json_indent: int = 2) -> None:
        self.prose_wrapper = ProseWrapper(wrap_width)
        self.json_indent = json_indent

    def normalize(self, text: str, kind: TextKind) -> str:
        if kind == "json":
            return format_json(text, self.json_indent)
        if kind == "jsonl":
            return format_jsonl(text)
        return self.prose_wrapper.wrap(normalize_line_endings(text))
