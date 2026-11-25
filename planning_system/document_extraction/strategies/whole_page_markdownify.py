"""markdownify of the whole page -> markdown"""
from __future__ import annotations

from lxml_html_clean import Cleaner
from markdownify import markdownify

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy, library_errors


class WholePageMarkdownify(ExtractionStrategy):
    name = "whole_page_markdownify"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        with library_errors():
            cleaned = Cleaner(scripts=True, javascript=True, style=True, comments=True, page_structure=False,
                              forms=False).clean_html(source.decoded_text())
            text = markdownify(cleaned, heading_style="ATX")
        return StrategyOutput(text, "markdown")
