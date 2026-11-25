"""trafilatura, output_format="markdown" -> markdown"""
from __future__ import annotations

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy


class TrafilaturaMarkdown(ExtractionStrategy):
    name = "trafilatura_markdown"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        raise NotImplementedError("level 7")
