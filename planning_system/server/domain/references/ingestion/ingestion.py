"""ingestion: synced user exchanges and node/proposal text into references; anything the reader
loads (URL, uploaded file, web search) -> document_extraction -> temp cache."""
import hashlib
import uuid
from dataclasses import dataclass
from typing import Mapping, Optional

from planning_system.document_extraction.extraction_interface import DocumentExtractor

from ..interface import TempCache
from ..ports import ReferenceStoragePort
from .source_fetcher_port import SourceFetcher, SourceRequest
from ..types import (ORIGIN_NODE, ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE, AgentId, Reference,
                    TempCacheEntry)


@dataclass(frozen=True)
class LoadedSource:
    """One source fetched live and extracted to text, ready for the reader's load."""
    text: str
    source_label: str
    extraction_info: Mapping[str, object]   # strategy_used, available_strategies, origin_kind, ...

    def metadata(self) -> dict:
        """extraction_info as string metadata (lists joined with commas)."""
        return {k: (v if isinstance(v, str) else ",".join(v)) for k, v in self.extraction_info.items()}


class Ingestion:
    def __init__(self, storage: ReferenceStoragePort, fetcher: Optional[SourceFetcher] = None,
                 extractor: Optional[DocumentExtractor] = None, temp_cache: Optional[TempCache] = None):
        self._storage = storage
        self._fetcher = fetcher
        self._extractor = extractor
        self._temp_cache = temp_cache

    def store(self, origin, text, metadata, owner=None) -> Reference:
        """Store one fixed item; identical content (same SHA-256) reuses the stored copy."""
        sha = hashlib.sha256(text.encode()).hexdigest()
        existing = self._storage.find_by_sha256(sha)
        if existing is not None:
            return existing
        ref = Reference(f"ref-{uuid.uuid4().hex}", origin, text, sha, dict(metadata), owner)
        self._storage.save(ref)
        return ref

    def store_user_exchange(self, session_id, user_message, pre_text):
        text = f"{pre_text}\n{user_message}" if pre_text else user_message
        return self.store(ORIGIN_USER_EXCHANGE, text, {"session_id": session_id})

    def store_proposal_response(self, node_id, text):
        return self.store(ORIGIN_PROPOSAL_RESPONSE, text, {"node_id": str(node_id)})

    def store_node_text(self, text, node_id):
        return self.store(ORIGIN_NODE, text, {"node_id": str(node_id)})

    def fetch_and_extract(self, source: SourceRequest, strategy: Optional[str] = None) -> LoadedSource:
        """Always fetches live. With strategy, only that extraction strategy runs.
        Raises FetchFailed, ExtractionFailed or UnknownStrategy."""
        if self._fetcher is None or self._extractor is None:
            raise RuntimeError("Ingestion was built without a source fetcher and document extractor")
        document = self._fetcher.fetch(source)
        result = self._extractor.extract(document, strategy)
        info = {"origin_kind": document.origin_kind, "locator": document.locator,
                "content_type": result.content_type, "raw_sha256": result.raw_sha256,
                "strategy_used": result.strategy_used,
                "available_strategies": list(result.available_strategies)}
        return LoadedSource(result.text, document.locator, info)

    def load_into_temp_cache(self, owner: AgentId, source: SourceRequest,
                             strategy: Optional[str] = None) -> TempCacheEntry:
        """Fetch live through the source fetcher, extract text, put it in the owner's temp cache."""
        if self._temp_cache is None:
            raise RuntimeError("Ingestion was built without a temp cache")
        loaded = self.fetch_and_extract(source, strategy)
        return self._temp_cache.put(owner, loaded.text, dict(loaded.metadata(), source_label=loaded.source_label))
