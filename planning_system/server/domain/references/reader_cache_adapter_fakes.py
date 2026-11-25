"""Test support: a working fake of ReaderCacheAdapter over the references fakes."""
import hashlib
import json

from planning_system.contract import Invalid, NotFound
from planning_system.fastreader.manifest_codec import manifest_from_dict, manifest_to_dict
from planning_system.fastreader.models import Document
from planning_system.fastreader.reader_cache_port import CachedItem, ReaderCachePort, ReaderCitation
from planning_system.fastreader.scanner import scan_document

from .reader_cache_adapter import MANIFEST_METADATA_KEY, ORIGIN_KIND_WEB_SEARCH


class FakeReaderCacheAdapter(ReaderCachePort):
    def __init__(self, temp_cache, library, agent_id, is_admin, scanner_config):
        self._temp_cache = temp_cache
        self._library = library
        self._agent_id = agent_id
        self._is_admin = is_admin
        self._scanner_config = scanner_config
        self._own_ids_by_sha: dict[str, str] = {}

    def save(self, text, manifest, source_label, metadata):
        sha = hashlib.sha256(text.encode()).hexdigest()
        if sha in self._own_ids_by_sha:
            return self._own_ids_by_sha[sha]
        stored = dict(metadata, source_label=source_label,
                      **{MANIFEST_METADATA_KEY: json.dumps(manifest_to_dict(manifest))})
        entry = self._temp_cache.put(self._agent_id, text, stored)
        self._own_ids_by_sha[sha] = entry.cache_id
        return entry.cache_id

    def _temp_entry_or_none(self, item_id):
        try:
            entry = self._temp_cache.get(item_id)
        except NotFound:
            return None
        if entry.owner != self._agent_id and not self._is_admin:
            raise NotFound(item_id)
        return entry

    def get(self, item_id):
        entry = self._temp_entry_or_none(item_id)
        if entry is not None:
            metadata = dict(entry.metadata)
            manifest = manifest_from_dict(json.loads(metadata.pop(MANIFEST_METADATA_KEY)))
            return CachedItem(item_id, metadata.get("source_label", item_id), entry.text,
                              manifest, metadata)
        ref = self._library.get(item_id)          # raises NotFound
        label = ref.metadata.get("source_label", ref.id)
        manifest = scan_document(Document.from_text(label, ref.text), self._scanner_config)
        return CachedItem(ref.id, label, ref.text, manifest, dict(ref.metadata))

    def cite(self, item_id, start_line, end_line):
        item = self.get(item_id)
        if item.metadata.get("origin_kind") == ORIGIN_KIND_WEB_SEARCH:
            raise Invalid("web search results can't be cited; load the result's URL first")
        if self._temp_entry_or_none(item_id) is not None:
            citation = self._temp_cache.cite(item_id, start_line, end_line)
            return ReaderCitation(citation.reference_id, citation.start_line, citation.end_line)
        self._library.read_lines(item_id, start_line, end_line)   # raises Invalid for a bad range
        return ReaderCitation(item_id, start_line, end_line)
