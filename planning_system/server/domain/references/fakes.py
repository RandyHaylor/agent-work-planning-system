"""Test support: in-memory stores, a settable clock, and fakes of ReferenceLibrary and TempCache."""
import dataclasses
import hashlib
import itertools
from datetime import datetime, timedelta, timezone

from planning_system.contract import Invalid, NotFound

from .interface import ReferenceLibrary, TempCache
from .ports import Clock, ReferenceStoragePort, TempCacheStoragePort
from .types import (ORIGIN_DOCUMENT, ORIGIN_NODE, ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE,
                    Citation, Reference, TempCacheEntry)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _lines(text, start, end):
    lines = text.splitlines()
    if start < 1 or end < start or end > len(lines):
        raise Invalid(f"lines {start}-{end} outside 1-{len(lines)}")
    return "\n".join(lines[start - 1:end])


class FakeClock(Clock):
    def __init__(self, start: datetime | None = None):
        self.current = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self):
        return self.current

    def advance(self, delta: timedelta):
        self.current += delta


class InMemoryReferenceStorage(ReferenceStoragePort):
    def __init__(self):
        self.rows: dict[str, Reference] = {}

    def get(self, ref_id):
        return self.rows.get(ref_id)

    def find_by_sha256(self, sha256):
        return next((r for r in self.rows.values() if r.sha256 == sha256), None)

    def save(self, reference):
        self.rows[reference.id] = reference


class InMemoryTempCacheStorage(TempCacheStoragePort):
    def __init__(self):
        self.rows: dict[str, TempCacheEntry] = {}

    def get(self, cache_id):
        return self.rows.get(cache_id)

    def save(self, entry):
        self.rows[entry.cache_id] = entry

    def delete(self, cache_id):
        self.rows.pop(cache_id, None)

    def created_before(self, cutoff):
        return [e for e in self.rows.values() if e.created_at < cutoff]


_ids = itertools.count(1)


class FakeReferenceLibrary(ReferenceLibrary):
    def __init__(self, storage: ReferenceStoragePort | None = None):
        self.storage = storage or InMemoryReferenceStorage()

    def _store(self, origin, text, metadata, owner=None):
        existing = self.storage.find_by_sha256(_sha(text))
        if existing is not None:
            return existing
        ref = Reference(f"ref-{next(_ids)}", origin, text, _sha(text), dict(metadata), owner)
        self.storage.save(ref)
        return ref

    def get(self, ref_id, follow_superseded=True):
        ref = self.storage.get(ref_id)
        if ref is None:
            raise NotFound(ref_id)
        while follow_superseded and ref.superseded_by is not None:
            ref = self.storage.get(ref.superseded_by)
        return ref

    def read_lines(self, ref_id, start, end):
        return _lines(self.get(ref_id, follow_superseded=False).text, start, end)

    def store_user_exchange(self, session_id, user_message, pre_text):
        text = f"{pre_text}\n{user_message}" if pre_text else user_message
        return self._store(ORIGIN_USER_EXCHANGE, text, {"session_id": session_id})

    def store_proposal_response(self, node_id, text):
        return self._store(ORIGIN_PROPOSAL_RESPONSE, text, {"node_id": str(node_id)})

    def store_node_text(self, text, node_id, replaces=None):
        new = self._store(ORIGIN_NODE, text, {"node_id": str(node_id)})
        if replaces is not None and replaces != new.id:
            self.supersede(replaces, new.id)
        return new

    def render(self, citation):
        return self.read_lines(citation.reference_id, citation.start_line, citation.end_line)

    def supersede(self, old_id, new_id):
        old = self.get(old_id, follow_superseded=False)
        self.get(new_id, follow_superseded=False)
        self.storage.save(dataclasses.replace(old, superseded_by=new_id))


class FakeTempCache(TempCache):
    def __init__(self, temp_storage, reference_storage, clock, ttl: timedelta = timedelta(days=7)):
        self._temp, self._refs, self._clock, self._ttl = temp_storage, reference_storage, clock, ttl

    def put(self, owner, text, metadata):
        entry = TempCacheEntry(f"tmp-{next(_ids)}", owner, text, _sha(text), self._clock.now(),
                               dict(metadata))
        self._temp.save(entry)
        return entry

    def get(self, cache_id):
        entry = self._temp.get(cache_id)
        if entry is None:
            raise NotFound(cache_id)
        return entry

    def cite(self, cache_id, start_line, end_line):
        entry = self._temp.get(cache_id)
        ref = self._refs.get(cache_id) or self._refs.find_by_sha256(_sha(entry.text) if entry else "")
        if ref is None:
            if entry is None:
                raise NotFound(cache_id)
            ref = Reference(cache_id, ORIGIN_DOCUMENT, entry.text, entry.sha256,
                            dict(entry.metadata), entry.owner)
        _lines(ref.text, start_line, end_line)
        self._refs.save(ref)
        self._temp.delete(cache_id)
        return Citation(ref.id, start_line, end_line)

    def purge_expired(self):
        old = self._temp.created_before(self._clock.now() - self._ttl)
        for entry in old:
            self._temp.delete(entry.cache_id)
        return len(old)
