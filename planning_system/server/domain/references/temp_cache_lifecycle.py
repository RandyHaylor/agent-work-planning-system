"""temp_cache_lifecycle: per-agent temp cache (separate store); cite moves an item into references; TTL purge."""
from datetime import timedelta

from .interface import TempCache


class TempCacheLifecycle(TempCache):
    def __init__(self, temp_storage, reference_storage, clock, ttl: timedelta = timedelta(days=7)):
        self._temp_storage = temp_storage
        self._reference_storage = reference_storage
        self._clock = clock
        self._ttl = ttl

    def put(self, owner, text, metadata):
        raise NotImplementedError

    def get(self, cache_id):
        raise NotImplementedError

    def cite(self, cache_id, start_line, end_line):
        raise NotImplementedError

    def purge_expired(self):
        raise NotImplementedError
