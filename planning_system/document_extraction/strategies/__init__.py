"""One strategy per extractor."""
from __future__ import annotations

from planning_system.document_extraction.strategies.trafilatura_markdown import TrafilaturaMarkdown
from planning_system.document_extraction.strategies.readabilipy_markdownify import ReadabilipyMarkdownify
from planning_system.document_extraction.strategies.whole_page_markdownify import WholePageMarkdownify
from planning_system.document_extraction.strategies.pypdf_text import PypdfText
from planning_system.document_extraction.strategies.pdfminer_text import PdfminerText
from planning_system.document_extraction.strategies.docx_text import DocxText
from planning_system.document_extraction.strategies.text_passthrough import TextPassthrough
from planning_system.document_extraction.strategies.json_pretty_print import JsonPrettyPrint
from planning_system.document_extraction.strategies.jsonl_passthrough import JsonlPassthrough
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy
from planning_system.document_extraction.strategies.strategy_registry import DEFAULT_ORDERS, StrategyRegistry


def default_strategies() -> tuple[ExtractionStrategy, ...]:
    return (TrafilaturaMarkdown(), ReadabilipyMarkdownify(), WholePageMarkdownify(), PypdfText(), PdfminerText(), DocxText(), TextPassthrough(), JsonPrettyPrint(), JsonlPassthrough())


__all__ = ["ExtractionStrategy", "StrategyRegistry", "DEFAULT_ORDERS", "default_strategies"]
