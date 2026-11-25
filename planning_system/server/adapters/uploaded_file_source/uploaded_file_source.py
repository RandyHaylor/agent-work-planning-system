"""File bytes uploaded by the CLI / local client (base64 already decoded by http_api)."""
from __future__ import annotations

from planning_system.server.domain.references.source_fetcher_port import FetchFailed, SourceFetcher, SourceRequest
from planning_system.document_extraction.extraction_types import SourceDocument


class UploadedFileSource(SourceFetcher):
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes

    def fetch(self, request: SourceRequest) -> SourceDocument:
        raise NotImplementedError("level 7")
