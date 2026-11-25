"""reader_cache_adapter: fastReader's ReaderCachePort over the per-agent TempCache + ReferenceLibrary.

Created per request for the acting principal. fastReader imports nothing from the server;
this adapter imports fastReader. Manifests are stored as JSON metadata ("manifest") next to
the text in the temp cache; a reference read into the reader is scanned on the fly.
"""
from typing import Any, Dict

from planning_system.fastreader.reader_cache_port import ReaderCachePort

from .interface import ReferenceLibrary, TempCache
from .types import AgentId

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

    def save(self, text, manifest, source_label, metadata):
        raise NotImplementedError

    def get(self, item_id):
        raise NotImplementedError

    def cite(self, item_id, start_line, end_line):
        raise NotImplementedError
