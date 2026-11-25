"""python-docx -> prose"""
from __future__ import annotations

import io

import docx

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy, library_errors


class DocxText(ExtractionStrategy):
    name = "docx_text"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        with library_errors():
            document = docx.Document(io.BytesIO(source.raw_bytes))
            text = "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
        return StrategyOutput(text, "prose")
