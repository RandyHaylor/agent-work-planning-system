"""Ingestion load path: source fetcher -> document_extraction -> temp cache, strategy reported,
--strategy runs only that strategy, loading always fetches live."""
from datetime import datetime, timezone

from planning_system.document_extraction.extraction_interface import DocumentExtractor
from planning_system.document_extraction.extraction_types import ExtractionResult, SourceDocument
from planning_system.server.domain.references.fakes import (FakeClock, InMemoryReferenceStorage,
                                                            InMemoryTempCacheStorage)
from planning_system.server.domain.references.ingestion.ingestion import Ingestion
from planning_system.server.domain.references.ingestion.source_fetcher_port import (SourceFetcher, UrlRequest,
                                                                          WebSearchRequest)
from planning_system.server.domain.references.temp_cache.temp_cache_lifecycle import TempCacheLifecycle


class CountingFetcher(SourceFetcher):
    def __init__(self):
        self.calls = []

    def fetch(self, request):
        self.calls.append(request)
        kind = "web_search" if isinstance(request, WebSearchRequest) else "web"
        locator = getattr(request, "url", None) or getattr(request, "terms", "")
        return SourceDocument(f"body {len(self.calls)}".encode(), locator, kind,
                              datetime(2026, 1, 1, tzinfo=timezone.utc), "text/plain")


class RecordingExtractor(DocumentExtractor):
    def __init__(self):
        self.strategies = []

    def extract(self, document, strategy=None):
        self.strategies.append(strategy)
        used = strategy or "plain_text"
        return ExtractionResult(document.raw_bytes.decode(), used, "text/plain", "t", "r", (),
                                ("plain_text", "html_text"))

    def strategy_names(self, content_type=None):
        return ("plain_text", "html_text")


def _ingestion():
    fetcher, extractor = CountingFetcher(), RecordingExtractor()
    cache = TempCacheLifecycle(InMemoryTempCacheStorage(), InMemoryReferenceStorage(), FakeClock())
    return Ingestion(InMemoryReferenceStorage(), fetcher, extractor, cache), fetcher, extractor, cache


def test_load_puts_extracted_text_in_the_owners_temp_cache_with_strategy():
    ingestion, _, _, cache = _ingestion()
    entry = ingestion.load_into_temp_cache("agent-1", UrlRequest("https://example.com"))
    stored = cache.get(entry.cache_id)
    assert stored.owner == "agent-1" and stored.text == "body 1"
    assert stored.metadata["strategy_used"] == "plain_text"
    assert stored.metadata["available_strategies"] == "plain_text,html_text"
    assert stored.metadata["origin_kind"] == "web"


def test_strategy_runs_only_that_strategy():
    ingestion, _, extractor, _ = _ingestion()
    loaded = ingestion.fetch_and_extract(UrlRequest("https://example.com"), strategy="html_text")
    assert extractor.strategies == ["html_text"] and loaded.extraction_info["strategy_used"] == "html_text"


def test_loading_the_same_url_twice_fetches_live_twice():
    ingestion, fetcher, _, _ = _ingestion()
    ingestion.fetch_and_extract(UrlRequest("https://example.com"))
    second = ingestion.fetch_and_extract(UrlRequest("https://example.com"))
    assert len(fetcher.calls) == 2 and second.text == "body 2"


def test_web_search_origin_is_recorded():
    ingestion, _, _, _ = _ingestion()
    loaded = ingestion.fetch_and_extract(WebSearchRequest("postgres ltree"))
    assert loaded.extraction_info["origin_kind"] == "web_search"
