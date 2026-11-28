"""File bytes uploaded by the CLI / local client (base64 already decoded by http_api)."""
from __future__ import annotations

from datetime import datetime, timezone

from planning_system.server.domain.references import FetchFailed, SourceFetcher, SourceRequest, UploadRequest
from planning_system.document_extraction.extraction_types import SourceDocument


class UploadedFileSource(SourceFetcher):
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes

    def fetch(self, request: SourceRequest) -> SourceDocument:
        if not isinstance(request, UploadRequest):
            raise TypeError(f"UploadedFileSource takes UploadRequest, got {type(request).__name__}")
        size = len(request.file_bytes)
        if size > self.max_bytes:
            raise FetchFailed(request.file_name, "too large")
        if size == 0:
            raise FetchFailed(request.file_name, "empty body")
        return SourceDocument(raw_bytes=request.file_bytes, locator=request.file_name, origin_kind="upload",
                              fetched_at=datetime.now(timezone.utc), content_type_header=None,
                              file_name=request.file_name, metadata={"size_bytes": str(size)})
