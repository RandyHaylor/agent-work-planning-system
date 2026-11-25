"""trafilatura, output_format="markdown" -> markdown"""
from __future__ import annotations

import trafilatura

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy, library_errors


class TrafilaturaMarkdown(ExtractionStrategy):
    name = "trafilatura_markdown"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        with library_errors():
            text = trafilatura.extract(source.decoded_text(), url=source.base_url, output_format="markdown",
                                       include_formatting=True, include_tables=True, include_links=False,
                                       with_metadata=False)
        return StrategyOutput(text or "", "markdown")
