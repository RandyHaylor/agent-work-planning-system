"""ingestion: turns a source request into stored references, through the SourceFetcher port.
Private child of references; import through `planning_system.server.domain.references`."""
from .ingestion import Ingestion
from .source_fetcher_port import (FetchFailed, SourceFetcher, SourceRequest, UploadRequest, UrlRequest,
    WebSearchRequest)

__all__ = ["FetchFailed", "Ingestion", "SourceFetcher", "SourceRequest", "UploadRequest", "UrlRequest",
           "WebSearchRequest"]
