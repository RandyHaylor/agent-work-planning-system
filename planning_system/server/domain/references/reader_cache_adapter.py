"""reader_cache_adapter: fastReader's ReaderCachePort over the per-agent TempCache + ReferenceLibrary.

Created per request for the acting principal. fastReader imports nothing from the server;
this adapter imports fastReader. Manifests are stored as JSON metadata ("manifest") next to
the text in the temp cache; a reference read into the reader is scanned on the fly.
"""
import hashlib
import json
from typing import Any, Dict

from planning_system.errors import Invalid, NotFound
from planning_system.fastreader.manifest_codec import manifest_from_dict, manifest_to_dict
from planning_system.fastreader.models import Document
from planning_system.fastreader.reader_cache_port import CachedItem, ReaderCachePort, ReaderCitation
from planning_system.fastreader.scanner import scan_document

from .interface import ReferenceLibrary, TempCache
from .types import AgentId, TempCacheEntry

MANIFEST_METADATA_KEY = "manifest"
ORIGIN_KIND_WEB_SEARCH = "web_search"


class ReaderCacheAdapter(ReaderCachePort):
    def __init__(self, temp_cache: TempCache, library: ReferenceLibrary, agent_id: AgentId,
                 is_admin: bool, scanner_config: Dict[str, Any]):
        self._temp_cache = temp_cache
        self._library = library
        self._agent_id = agent_id
        self._is_admin = is_admin
        self._scanner_config = scanner_config
        # The temp cache port has no lookup by content, so "identical text returns its id" holds
        # for loads made through this adapter instance (one request).
        self._own_ids_by_sha: Dict[str, str] = {}

    def save(self, text, manifest, source_label, metadata):
        sha = hashlib.sha256(text.encode()).hexdigest()
        known = self._own_ids_by_sha.get(sha)
        if known is not None and self._visible_temp_entry(known) is not None:
            return known
        stored = dict(metadata, source_label=source_label,
                      **{MANIFEST_METADATA_KEY: json.dumps(manifest_to_dict(manifest))})
        entry = self._temp_cache.put(self._agent_id, text, stored)
        self._own_ids_by_sha[sha] = entry.cache_id
        return entry.cache_id

    def get(self, item_id):
        entry = self._visible_temp_entry(item_id)
        if entry is not None:
            metadata = dict(entry.metadata)
            label = metadata.get("source_label", item_id)
            encoded = metadata.pop(MANIFEST_METADATA_KEY, None)
            manifest = manifest_from_dict(json.loads(encoded)) if encoded else self._scan(label, entry.text)
            return CachedItem(item_id, label, entry.text, manifest, metadata)
        ref = self._library.get(item_id)          # raises NotFound
        metadata = {k: v for k, v in ref.metadata.items() if k != MANIFEST_METADATA_KEY}
        label = metadata.get("source_label", ref.id)
        return CachedItem(ref.id, label, ref.text, self._scan(label, ref.text), metadata)

    def cite(self, item_id, start_line, end_line):
        item = self.get(item_id)
        if item.metadata.get("origin_kind") == ORIGIN_KIND_WEB_SEARCH:
            raise Invalid("web search results can't be cited; load the result's URL first")
        if self._visible_temp_entry(item_id) is not None:
            citation = self._temp_cache.cite(item_id, start_line, end_line)
            return ReaderCitation(citation.reference_id, citation.start_line, citation.end_line)
        self._library.read_lines(item.item_id, start_line, end_line)   # raises Invalid for a bad range
        return ReaderCitation(item.item_id, start_line, end_line)

    def _visible_temp_entry(self, item_id) -> TempCacheEntry | None:
        """The caller's temp entry (or any, for admin); another agent's entry is NotFound."""
        try:
            entry = self._temp_cache.get(item_id)
        except NotFound:
            return None
        if entry.owner != self._agent_id and not self._is_admin:
            raise NotFound(item_id)
        return entry

    def _scan(self, label, text):
        return scan_document(Document.from_text(label, text), self._scanner_config)
