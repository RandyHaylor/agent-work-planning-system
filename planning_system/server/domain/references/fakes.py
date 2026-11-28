"""Test support: in-memory stores, a settable clock, and fakes of ReferenceLibrary and TempCache."""
import dataclasses
import hashlib
import itertools
import re
from datetime import datetime, timedelta, timezone

from planning_system.errors import Conflict, Invalid, NotFound

from .interface import ReferenceLibrary, TempCache
from .related import RelatedFound, RelatedReferences, content_terms, summary
from .supersede import (SupersedeCandidate, SupersedeCandidateStoragePort, SupersedeCandidates,
                        candidate_kind)
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

    def find_by_locator(self, locator):
        return sorted((r for r in self.rows.values() if r.superseded_by is None
                       and r.metadata.get("locator") == locator), key=lambda r: r.id)

    def search_text(self, terms, limit):
        wanted = {t.lower() for t in terms}
        scored = []
        for r in self.rows.values():
            if r.superseded_by is None:
                score = len(wanted & set(re.findall(r"[a-z0-9]+", r.text.lower())))
                if score:
                    scored.append((-score, r.id, r))
        return [r for _, _, r in sorted(scored)[:limit]]


class FakeRelatedReferences(RelatedReferences):
    """Same answers as RelatedReferenceFinder for simple cases, computed straight from the rows."""

    def __init__(self, storage: InMemoryReferenceStorage):
        self._rows = storage.rows

    def _current(self):
        return [r for r in self._rows.values() if r.superseded_by is None and r.origin != ORIGIN_NODE]

    def related(self, locator, text, exclude_id=None, limit=5):
        same = [r for r in self._current() if locator and r.metadata.get("locator") == locator and r.id != exclude_id]
        skip = {exclude_id, *(r.id for r in same)}
        terms = set(content_terms(text))
        topic = sorted(((len(terms & set(re.findall(r"[a-z0-9]+", r.text.lower()))), r) for r in self._current()
                        if r.id not in skip), key=lambda pair: (-pair[0], pair[1].id))
        return RelatedFound(tuple(summary(r) for r in sorted(same, key=lambda r: r.id)),
                            tuple(summary(r) for score, r in topic if score)[:limit])

    def search(self, query, limit=10):
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        hits = sorted(((len(terms & set(re.findall(r"[a-z0-9]+", r.text.lower()))), r) for r in self._current()),
                      key=lambda pair: (-pair[0], pair[1].id))
        return [summary(r) for score, r in hits if score][:limit]


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


class InMemorySupersedeCandidateStorage(SupersedeCandidateStoragePort):
    def __init__(self):
        self.rows: dict[str, SupersedeCandidate] = {}

    def add(self, candidate):
        self.rows[candidate.id] = candidate

    def get(self, candidate_id):
        return self.rows.get(candidate_id)

    def save(self, candidate):
        self.rows[candidate.id] = candidate

    def find(self, project_id=None, status=None, old_reference_id=None, new_reference_id=None):
        return sorted((c for c in self.rows.values()
                       if (project_id is None or c.project_id == project_id) and (status is None or c.status == status)
                       and (old_reference_id is None or c.old_reference_id == old_reference_id)
                       and (new_reference_id is None or c.new_reference_id == new_reference_id)),
                      key=lambda c: (c.created_at, c.id))


class FakeSupersedeCandidates(SupersedeCandidates):
    """Compact working version over a plain dict and any ReferenceLibrary."""

    def __init__(self, library: ReferenceLibrary, clock: Clock | None = None):
        self._library, self._clock = library, clock or FakeClock()
        self._rows: dict[str, SupersedeCandidate] = {}
        self._ids = itertools.count(1)

    def propose(self, project_id, old_reference_id, new_reference_id, found_by, proposed_by, reason=""):
        if old_reference_id == new_reference_id:
            raise Invalid("a reference can't supersede itself")
        for c in self._rows.values():
            if (c.project_id, c.old_reference_id, c.new_reference_id) == (project_id, old_reference_id,
                                                                          new_reference_id):
                return c, False
        old = self._library.get(old_reference_id, follow_superseded=False)
        new = self._library.get(new_reference_id, follow_superseded=False)
        if old.superseded_by:
            raise Invalid(f"{old.id} is already superseded by {old.superseded_by}")
        candidate = SupersedeCandidate(f"sup-fake-{next(self._ids)}", project_id, old.id, new.id,
                                       candidate_kind(old.origin, new.origin), found_by, "proposed", proposed_by,
                                       reason, self._clock.now())
        self._rows[candidate.id] = candidate
        return candidate, True

    def get(self, candidate_id):
        if candidate_id not in self._rows:
            raise NotFound(f"supersede candidate {candidate_id}")
        return self._rows[candidate_id]

    def list(self, project_id, status=None):
        return [c for c in self._rows.values() if c.project_id == project_id and status in (None, c.status)]

    def mark_trial_reviewed(self, candidate_id, request_node_id):
        return self._set(self._open(candidate_id), status="trial_reviewed", request_node_id=request_node_id)

    def confirm(self, candidate_id, decided_by):
        candidate = self._open(candidate_id)
        self._library.supersede(candidate.old_reference_id, candidate.new_reference_id)
        return self._set(candidate, status="confirmed", decided_by=decided_by, decided_at=self._clock.now())

    def reject(self, candidate_id, decided_by, reason):
        return self._set(self._open(candidate_id), status="rejected", decided_by=decided_by, reason=reason,
                         decided_at=self._clock.now())

    def _open(self, candidate_id):
        candidate = self.get(candidate_id)
        if candidate.status not in ("proposed", "trial_reviewed"):
            raise Conflict(f"supersede candidate {candidate_id} is already {candidate.status}")
        return candidate

    def _set(self, candidate, **changes):
        self._rows[candidate.id] = dataclasses.replace(candidate, **changes)
        return self._rows[candidate.id]
