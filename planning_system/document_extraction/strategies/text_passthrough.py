"""decoded text as is -> plain (markdown files -> markdown); fails on undecodable binary"""
from __future__ import annotations

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyFailed, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy

_BINARY_SAMPLE_BYTES = 8192
_MAX_REPLACEMENT_RATIO = 0.1


def _looks_binary(raw_bytes: bytes, text: str) -> bool:
    """NUL bytes, or many replacement characters after decoding, mean the bytes are not text."""
    if b"\x00" in raw_bytes[:_BINARY_SAMPLE_BYTES] and not raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    sample = text[:_BINARY_SAMPLE_BYTES]
    return bool(sample) and sample.count("�") / len(sample) > _MAX_REPLACEMENT_RATIO


class TextPassthrough(ExtractionStrategy):
    name = "text_passthrough"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        text = source.decoded_text()
        if _looks_binary(source.raw_bytes, text):
            raise StrategyFailed("undecodable binary")
        return StrategyOutput(text, "markdown" if source.content_type == "text/markdown" else "plain")
