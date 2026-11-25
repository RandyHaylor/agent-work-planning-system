"""readabilipy (pure Python, use_readability=False) + markdownify -> markdown"""
from __future__ import annotations

from markdownify import markdownify
from readabilipy import simple_json_from_html_string

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy, library_errors


class ReadabilipyMarkdownify(ExtractionStrategy):
    name = "readabilipy_markdownify"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        with library_errors():
            article = simple_json_from_html_string(source.decoded_text(), use_readability=False)
            body = markdownify(article.get("content") or "", heading_style="ATX")
        if not body.strip():
            return StrategyOutput("", "markdown")
        title = (article.get("title") or "").strip()
        return StrategyOutput((f"# {title}\n\n" if title else "") + body, "markdown")
