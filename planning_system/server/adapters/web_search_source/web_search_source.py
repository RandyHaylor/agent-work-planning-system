"""Search terms -> markdown result page (## title, URL, snippet per result), fetched through the
HTTP fetcher and parsed with fastReader's kept DuckDuckGo scraper logic."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

from planning_system.server.adapters.web_search_source.ddg_result_parser import parse_results
from planning_system.server.domain.references import (SourceFetcher, SourceRequest, UrlRequest,
                                                      WebSearchRequest)
from planning_system.document_extraction.extraction_types import SourceDocument

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"


class WebSearchSource(SourceFetcher):
    def __init__(self, http_fetcher: SourceFetcher) -> None:
        self.http_fetcher = http_fetcher

    def fetch(self, request: SourceRequest) -> SourceDocument:
        if not isinstance(request, WebSearchRequest):
            raise TypeError(f"WebSearchSource takes WebSearchRequest, got {type(request).__name__}")
        url = f"{DUCKDUCKGO_HTML_URL}?{urllib.parse.urlencode({'q': request.terms})}"
        page = self.http_fetcher.fetch(UrlRequest(url)).raw_bytes.decode("utf-8", errors="replace")
        parsed = parse_results(page, request.limit)
        return SourceDocument(raw_bytes=parsed.text.encode("utf-8"), locator=request.terms,
                              origin_kind="web_search", fetched_at=datetime.now(timezone.utc),
                              content_type_header="text/markdown", file_name=None,
                              metadata={"engine": "duckduckgo", "result_count": str(parsed.result_count)})
