"""quote_capture_bridge: adapts quote_capture's classes to the two ports LocalClient calls."""
from __future__ import annotations

from dataclasses import asdict

from .interface import ExchangeReaderPort, ReferenceId, ReferenceSyncPort
from .quote_capture.interface import ReferenceSync
from .quote_capture.jsonl_exchange_cache import JsonlExchangeCache


class CachedExchangeReader(ExchangeReaderPort):

    def __init__(self, cache: JsonlExchangeCache):
        self._cache = cache

    def recent_exchanges(self, last: int) -> list[dict]:
        return [{**asdict(e), "captured_at": e.captured_at.isoformat()} for e in self._cache.recent(last)]


class ReferenceSyncAdapter(ReferenceSyncPort):

    def __init__(self, reference_sync: ReferenceSync):
        self._reference_sync = reference_sync

    def sync(self, local_exchange_id: str) -> ReferenceId:
        return self._reference_sync.sync(local_exchange_id)
