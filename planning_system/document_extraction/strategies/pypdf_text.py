"""pypdf -> prose"""
from __future__ import annotations

import io

from pypdf import PdfReader

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy, library_errors


class PypdfText(ExtractionStrategy):
    name = "pypdf_text"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        with library_errors():
            pages = PdfReader(io.BytesIO(source.raw_bytes)).pages
            text = "\n\n".join(page.extract_text() or "" for page in pages)
        return StrategyOutput(text, "prose")
