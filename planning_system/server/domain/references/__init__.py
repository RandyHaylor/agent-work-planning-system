"""references: ReferenceLibrary, temp cache, citations (spec: planning/05-spec-references-and-reader.md).

Public surface: import from this package, not its files. `fakes` stays a separate
test-support submodule. Nested children: `citation_syntax` (pure citation text form; other
domain packages and http_api depend on it alone) and `reader` (all fastReader/quick-json-reader coupling)."""
from .citation_syntax import citations_in, cites, format_citation, parse_citation, slice_lines
from .ingestion import Ingestion
from .interface import Reader, ReferenceLibrary, TempCache
from .line_range_mapping import map_line_range
from .ports import Clock, ReferenceStoragePort, TempCacheStoragePort
from .reader import ReaderService, numbered
from .reference_library import ReferenceLibraryService
from .source_fetcher_port import (FetchFailed, SourceFetcher, SourceRequest, UploadRequest, UrlRequest,
    WebSearchRequest)
from .temp_cache_lifecycle import TempCacheLifecycle
from .types import (AgentId, CacheId, Citation, NodeId, ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE, ORIGIN_NODE,
    ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE, Reference, ReferenceId, TempCacheEntry)

__all__ = ["AgentId", "CacheId", "Citation", "Clock", "FetchFailed", "Ingestion", "NodeId",
           "ORIGIN_DOCUMENT", "ORIGIN_KNOWLEDGE_BASE", "ORIGIN_NODE", "ORIGIN_PROPOSAL_RESPONSE",
           "ORIGIN_USER_EXCHANGE", "Reader", "ReaderService", "Reference", "ReferenceId", "ReferenceLibrary",
           "ReferenceLibraryService", "ReferenceStoragePort", "SourceFetcher", "SourceRequest", "TempCache",
           "TempCacheEntry", "TempCacheLifecycle", "TempCacheStoragePort", "UploadRequest", "UrlRequest",
           "WebSearchRequest", "citations_in", "cites", "format_citation", "map_line_range", "numbered",
           "parse_citation", "slice_lines"]
