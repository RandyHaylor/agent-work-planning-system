from __future__ import annotations

import httpx

from planning_system.server.domain.references.source_fetcher_port import FetchFailed, SourceFetcher, SourceRequest
from planning_system.document_extraction.extraction_types import SourceDocument


class HttpSourceFetcher(SourceFetcher):
    """Always a live GET (Cache-Control: no-cache); never consults the temp cache or references."""

    def __init__(self, client: httpx.Client, max_bytes: int) -> None:
        self.client = client
        self.max_bytes = max_bytes

    def fetch(self, request: SourceRequest) -> SourceDocument:
        raise NotImplementedError("level 7")
