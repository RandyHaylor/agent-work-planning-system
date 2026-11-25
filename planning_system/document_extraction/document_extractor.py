"""Facade: detect type -> pick strategy list -> fallback_runner -> text_normalization -> hash."""
from __future__ import annotations

import hashlib
from functools import cache
from typing import Mapping, Sequence

from planning_system.document_extraction.content_type_detection import LayeredContentTypeDetector
from planning_system.document_extraction.extraction_interface import (
    ContentTypeDetector, DocumentExtractor, StrategyCatalog, TextDecoder, TextNormalizer,
)
from planning_system.document_extraction.extraction_types import (
    AttemptRecord, ExtractionFailed, ExtractionInput, ExtractionResult, SourceDocument, StrategyFailed,
    StrategyOutput,
)
from planning_system.document_extraction.fallback_runner import (
    AllStrategiesFailed, FallbackRunner, FallbackRunnerInterface,
)
from planning_system.document_extraction.strategies import (
    DEFAULT_ORDERS, ExtractionStrategy, StrategyRegistry, default_strategies,
)
from planning_system.document_extraction.text_decoding import ChainedTextDecoder
from planning_system.document_extraction.text_normalization import KindTextNormalizer


class _StrategyCall:
    """Adapts an ExtractionStrategy to the generic runner; empty output counts as failure."""

    def __init__(self, strategy: ExtractionStrategy) -> None:
        self.strategy = strategy
        self.name = strategy.name

    def __call__(self, source: ExtractionInput) -> StrategyOutput:
        output = self.strategy.extract(source)
        if not output.text.strip():
            raise StrategyFailed("empty output")
        return output


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class StrategyDocumentExtractor(DocumentExtractor):
    def __init__(self, detector: ContentTypeDetector, decoder: TextDecoder, catalog: StrategyCatalog,
                 runner: FallbackRunnerInterface, normalizer: TextNormalizer) -> None:
        self.detector = detector
        self.decoder = decoder
        self.catalog = catalog
        self.runner = runner
        self.normalizer = normalizer

    def extract(self, document: SourceDocument, strategy: str | None = None) -> ExtractionResult:
        content_type = self.detector.detect(document.raw_bytes, document.content_type_header, document.file_name)
        names = (strategy,) if strategy else self.catalog.default_order(content_type)
        calls = [_StrategyCall(self.catalog.get(name)) for name in names]
        source = self._extraction_input(document, content_type)
        try:
            outcome = self.runner.run(source, calls)
        except AllStrategiesFailed as failure:
            raise ExtractionFailed(tuple(AttemptRecord(a.strategy, a.error) for a in failure.attempts)) from failure
        text = self.normalizer.normalize(outcome.output.text, outcome.output.kind)
        return ExtractionResult(
            text=text, strategy_used=outcome.used_name, content_type=content_type,
            text_sha256=sha256_hex(text.encode("utf-8")), raw_sha256=sha256_hex(document.raw_bytes),
            attempts=tuple(AttemptRecord(a.strategy, a.error) for a in outcome.attempts),
            available_strategies=self.catalog.default_order(content_type))

    def strategy_names(self, content_type: str | None = None) -> tuple[str, ...]:
        return self.catalog.default_order(content_type) if content_type else self.catalog.names()

    def _extraction_input(self, document: SourceDocument, content_type: str) -> ExtractionInput:
        decode = cache(lambda: self.decoder.decode(document.raw_bytes, document.content_type_header))
        base_url = document.metadata.get("final_url") or (document.locator if document.origin_kind == "web" else None)
        return ExtractionInput(document.raw_bytes, content_type, decode, base_url)


def build_document_extractor(config: Mapping, strategies: Sequence[ExtractionStrategy] | None = None
                             ) -> DocumentExtractor:
    """Factory; `config` is the "document_extraction" section. `strategies` overrides the defaults (tests)."""
    return StrategyDocumentExtractor(
        detector=LayeredContentTypeDetector(),
        decoder=ChainedTextDecoder(),
        catalog=StrategyRegistry(strategies if strategies is not None else default_strategies(),
                                 config.get("strategy_orders", DEFAULT_ORDERS)),
        runner=FallbackRunner(StrategyFailed),
        normalizer=KindTextNormalizer(config.get("wrap_width", 100), config.get("json_indent", 2)))
