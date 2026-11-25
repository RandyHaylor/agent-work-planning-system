"""name -> strategy; default order per content type (config, overridable)."""
from __future__ import annotations

from typing import Mapping, Sequence

from planning_system.document_extraction.extraction_interface import StrategyCatalog
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy

HTML_ORDER = ("trafilatura_markdown", "readabilipy_markdownify", "whole_page_markdownify")
DEFAULT_ORDERS: Mapping[str, tuple[str, ...]] = {
    "text/html": HTML_ORDER,
    "application/xhtml+xml": HTML_ORDER,
    "application/pdf": ("pypdf_text", "pdfminer_text"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("docx_text",),
    "application/json": ("json_pretty_print", "text_passthrough"),
    "application/x-ndjson": ("jsonl_passthrough", "text_passthrough"),
    "application/jsonl": ("jsonl_passthrough", "text_passthrough"),
    "text/*": ("text_passthrough",),
    "*": ("text_passthrough",),
}


class StrategyRegistry(StrategyCatalog):
    def __init__(self, strategies: Sequence[ExtractionStrategy],
                 default_orders: Mapping[str, Sequence[str]] = DEFAULT_ORDERS) -> None:
        self.strategies = tuple(strategies)
        self.default_orders = default_orders

    def get(self, name: str) -> ExtractionStrategy:
        raise NotImplementedError("level 7")

    def default_order(self, content_type: str) -> tuple[str, ...]:
        raise NotImplementedError("level 7")

    def names(self) -> tuple[str, ...]:
        raise NotImplementedError("level 7")
