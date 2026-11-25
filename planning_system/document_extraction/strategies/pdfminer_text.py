"""pdfminer.six -> prose"""
from __future__ import annotations

import io

from pdfminer.high_level import extract_text

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy, library_errors


class PdfminerText(ExtractionStrategy):
    name = "pdfminer_text"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        with library_errors():
            text = extract_text(io.BytesIO(source.raw_bytes))
        return StrategyOutput(text.replace("\f", "\n"), "prose")
