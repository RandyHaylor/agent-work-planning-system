"""decoded text as is -> plain (markdown files -> markdown); fails on undecodable binary"""
from __future__ import annotations

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy


class TextPassthrough(ExtractionStrategy):
    name = "text_passthrough"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        raise NotImplementedError("level 7")
