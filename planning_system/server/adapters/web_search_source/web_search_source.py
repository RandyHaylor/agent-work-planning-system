"""Search terms -> markdown result page (## title, URL, snippet per result), fetched through the
HTTP fetcher and parsed with fastReader's kept DuckDuckGo scraper functions."""
from __future__ import annotations

from planning_system.server.domain.references.source_fetcher_port import SourceFetcher, SourceRequest
from planning_system.document_extraction.extraction_types import SourceDocument

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"


class WebSearchSource(SourceFetcher):
    def __init__(self, http_fetcher: SourceFetcher) -> None:
        self.http_fetcher = http_fetcher

    def fetch(self, request: SourceRequest) -> SourceDocument:
        raise NotImplementedError("level 7")
