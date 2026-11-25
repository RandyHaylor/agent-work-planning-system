"""temp_cache_lifecycle: per-agent temp cache (separate store); cite moves an item into references; TTL purge."""
import hashlib
import uuid
from datetime import timedelta

from planning_system.contract import NotFound

from .citing_and_rendering import slice_lines
from .interface import TempCache
from .ports import Clock, ReferenceStoragePort, TempCacheStoragePort
from .types import ORIGIN_DOCUMENT, Citation, Reference, TempCacheEntry


class TempCacheLifecycle(TempCache):
    def __init__(self, temp_storage: TempCacheStoragePort, reference_storage: ReferenceStoragePort,
                 clock: Clock, ttl: timedelta = timedelta(days=7)):
        self._temp_storage = temp_storage
        self._reference_storage = reference_storage
        self._clock = clock
        self._ttl = ttl

    def put(self, owner, text, metadata):
        entry = TempCacheEntry(f"tmp-{uuid.uuid4().hex}", owner, text,
                               hashlib.sha256(text.encode()).hexdigest(), self._clock.now(), dict(metadata))
        self._temp_storage.save(entry)
        return entry

    def get(self, cache_id):
        entry = self._temp_storage.get(cache_id)
        if entry is None:
            raise NotFound(cache_id)
        return entry

    def cite(self, cache_id, start_line, end_line):
        """Validate the range, then move the entry into references keeping its id; identical content
        already in references is reused (its id is returned). Citing an id already moved just cites it."""
        already = self._reference_storage.get(cache_id)
        if already is not None:
            slice_lines(already.text, start_line, end_line)
            return Citation(already.id, start_line, end_line)
        entry = self.get(cache_id)
        slice_lines(entry.text, start_line, end_line)
        ref = self._reference_storage.find_by_sha256(entry.sha256)
        if ref is None:
            ref = Reference(entry.cache_id, ORIGIN_DOCUMENT, entry.text, entry.sha256,
                            dict(entry.metadata), entry.owner)
            self._reference_storage.save(ref)
        self._temp_storage.delete(cache_id)
        return Citation(ref.id, start_line, end_line)

    def purge_expired(self):
        expired = self._temp_storage.created_before(self._clock.now() - self._ttl)
        for entry in expired:
            self._temp_storage.delete(entry.cache_id)
        return len(expired)
