from __future__ import annotations

from datetime import datetime, timezone

import httpx

from planning_system.document_extraction.extraction_types import SourceDocument
from planning_system.server.adapters.http_source_fetcher.failure_markers import failure_reason
from planning_system.server.domain.references import FetchFailed, SourceFetcher, SourceRequest, UrlRequest

_KEPT_HEADERS = ("etag", "last-modified")


class HttpSourceFetcher(SourceFetcher):
    """Always a live GET (Cache-Control: no-cache); never consults the temp cache or references."""

    def __init__(self, client: httpx.Client, max_bytes: int) -> None:
        self.client = client
        self.max_bytes = max_bytes

    def fetch(self, request: SourceRequest) -> SourceDocument:
        if not isinstance(request, UrlRequest):
            raise TypeError(f"HttpSourceFetcher takes UrlRequest, got {type(request).__name__}")
        url = request.url
        try:
            with self.client.stream("GET", url, headers={"Cache-Control": "no-cache"}) as response:
                body = self._read_capped(url, response)
                status, headers, final_url = response.status_code, response.headers, str(response.url)
        except httpx.TimeoutException as error:
            raise FetchFailed(url, "timeout") from error
        except httpx.HTTPError as error:
            raise FetchFailed(url, f"request error: {type(error).__name__}") from error
        reason = failure_reason(status, headers, body)
        if reason:
            raise FetchFailed(url, reason, status)
        fetched_at = datetime.now(timezone.utc)
        metadata = {"final_url": final_url, "status": str(status), "fetched_at": fetched_at.isoformat()}
        metadata.update({name: headers[name] for name in _KEPT_HEADERS if name in headers})
        return SourceDocument(raw_bytes=body, locator=url, origin_kind="web", fetched_at=fetched_at,
                              content_type_header=headers.get("content-type"), file_name=None, metadata=metadata)

    def _read_capped(self, url: str, response: httpx.Response) -> bytes:
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > self.max_bytes:
                raise FetchFailed(url, "too large", response.status_code)
            chunks.append(chunk)
        return b"".join(chunks)
