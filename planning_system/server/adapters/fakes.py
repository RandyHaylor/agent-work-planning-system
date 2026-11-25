"""In-memory fakes of the source fetcher adapters (build log #11). Same contracts, no network."""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from typing import Mapping

from planning_system.document_extraction.extraction_types import SourceDocument
from planning_system.fastreader.web import html_to_text
from planning_system.server.adapters.web_search_source import DUCKDUCKGO_HTML_URL
from planning_system.server.domain.references.source_fetcher_port import (
    FetchFailed, SourceFetcher, SourceRequest, UploadRequest, UrlRequest, WebSearchRequest,
)


@dataclass(frozen=True)
class FakeResponse:
    status: int = 200
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    final_url: str | None = None  # set when the request was redirected
    timeout: bool = False


class FakeHttpSourceFetcher(SourceFetcher):
    """Serves scripted responses by URL and applies the same failure markers as the real fetcher."""

    def __init__(self, responses: Mapping[str, FakeResponse], max_bytes: int = 25 * 1024 * 1024) -> None:
        self.responses = dict(responses)
        self.max_bytes = max_bytes
        self.requested: list[str] = []

    def fetch(self, request: SourceRequest) -> SourceDocument:
        assert isinstance(request, UrlRequest)
        self.requested.append(request.url)
        response = self.responses[request.url]
        if response.timeout:
            raise FetchFailed(request.url, "timeout")
        headers = {k.lower(): v for k, v in response.headers.items()}
        if response.status >= 400 and headers.get("cf-mitigated") == "challenge":
            raise FetchFailed(request.url, "cloudflare challenge (cf-mitigated)", response.status)
        if response.status >= 400:
            raise FetchFailed(request.url, f"http {response.status}", response.status)
        if len(response.body) > self.max_bytes:
            raise FetchFailed(request.url, "too large", response.status)
        if not response.body:
            raise FetchFailed(request.url, "empty body", response.status)
        fetched_at = datetime.now(timezone.utc)
        metadata = {"final_url": response.final_url or request.url, "status": str(response.status),
                    "fetched_at": fetched_at.isoformat()}
        metadata.update({k: headers[k] for k in ("etag", "last-modified") if k in headers})
        return SourceDocument(raw_bytes=response.body, locator=request.url, origin_kind="web",
                              fetched_at=fetched_at, content_type_header=headers.get("content-type"),
                              file_name=None, metadata=metadata)


class FakeUploadedFileSource(SourceFetcher):
    def __init__(self, max_bytes: int = 25 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def fetch(self, request: SourceRequest) -> SourceDocument:
        assert isinstance(request, UploadRequest)
        if len(request.file_bytes) > self.max_bytes:
            raise FetchFailed(request.file_name, "too large")
        return SourceDocument(raw_bytes=request.file_bytes, locator=request.file_name, origin_kind="upload",
                              fetched_at=datetime.now(timezone.utc), content_type_header=None,
                              file_name=request.file_name, metadata={"size_bytes": str(len(request.file_bytes))})


_RESULT_BLOCK = re.compile(
    r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</span>',
    re.DOTALL)


class FakeWebSearchSource(SourceFetcher):
    """Fetches the DuckDuckGo HTML page through the given HTTP fetcher; same parse as fastReader's search_ddg."""

    def __init__(self, http_fetcher: SourceFetcher) -> None:
        self.http_fetcher = http_fetcher

    def fetch(self, request: SourceRequest) -> SourceDocument:
        assert isinstance(request, WebSearchRequest)
        url = f"{DUCKDUCKGO_HTML_URL}?{urllib.parse.urlencode({'q': request.terms})}"
        page = self.http_fetcher.fetch(UrlRequest(url)).raw_bytes.decode("utf-8", errors="replace")
        results = [f"## {html_to_text(title).strip()}\n{unescape(href)}\n\n{html_to_text(snippet).strip()}\n"
                   for href, title, snippet in _RESULT_BLOCK.findall(page)[:request.limit]]
        text = "\n".join(results) if results else html_to_text(page)
        return SourceDocument(raw_bytes=text.encode("utf-8"), locator=request.terms, origin_kind="web_search",
                              fetched_at=datetime.now(timezone.utc), content_type_header="text/markdown",
                              file_name=None, metadata={"engine": "duckduckgo", "result_count": str(len(results))})
