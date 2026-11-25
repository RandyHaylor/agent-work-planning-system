"""python-docx -> prose"""
from __future__ import annotations

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy


class DocxText(ExtractionStrategy):
    name = "docx_text"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        raise NotImplementedError("level 7")
