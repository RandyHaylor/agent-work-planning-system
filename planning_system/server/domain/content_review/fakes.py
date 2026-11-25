"""Test support: InMemoryReviewStorage (the storage port in memory; no row locks, one process) and
FakeReviewLedger (a compact ledger over a plain dict; packets resolve quotes the simple way)."""
from __future__ import annotations

import dataclasses
import itertools
from datetime import datetime, timedelta, timezone

from planning_system.contract import Conflict, NotFound
from planning_system.server.domain.references.citation_format import citations_in
from planning_system.server.domain.references.types import ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE

from .interface import ReviewLedger
from .ports import Clock, ReviewStoragePort
from .types import (BLOCKING_STATUSES, DEFAULT_LEASE, FAILED, PASSED, PENDING, SUPERSEDED, TAKEN,
                    ResolvedCitation, ReviewPacket, ReviewRecord)


class TickingClock(Clock):
    def __init__(self, start: datetime | None = None, step: timedelta = timedelta(seconds=1)):
        self.current = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.step = step

    def now(self):
        self.current += self.step
        return self.current

    def advance(self, delta: timedelta):
        self.current += delta


class InMemoryReviewStorage(ReviewStoragePort):
    def __init__(self):
        self._records: dict[str, ReviewRecord] = {}

    def add(self, record):
        self._records[record.id] = record

    def get(self, review_id):
        return self._records.get(review_id)

    def save(self, record):
        self._records[record.id] = record

    def find(self, project_id=None, statuses=None, node_id=None, content_reference_id=None):
        statuses = None if statuses is None else set(statuses)
        found = [r for r in self._records.values()
                 if (project_id is None or r.project_id == project_id)
                 and (statuses is None or r.status in statuses)
                 and (node_id is None or r.node_id == node_id)
                 and (content_reference_id is None or r.content_reference_id == content_reference_id)]
        return sorted(found, key=lambda r: (r.created_at, r.id))

    def lock_oldest_pending(self, project_id):
        pending = self.find(project_id, (PENDING,))
        return pending[0] if pending else None

    def taken_before(self, cutoff):
        return [r for r in self.find(statuses=(TAKEN,)) if r.taken_at is not None and r.taken_at < cutoff]


class FakeReviewLedger(ReviewLedger):
    def __init__(self, references, tree, clock: Clock | None = None, lease: timedelta = DEFAULT_LEASE):
        self._references, self._tree = references, tree
        self._clock = clock or TickingClock()
        self._lease = lease
        self._records: dict[str, ReviewRecord] = {}
        self._ids = itertools.count(1)

    def open(self, project_id, node_id, content_reference_id, claim_tag):
        record = ReviewRecord(f"rev-fake-{next(self._ids)}", project_id, node_id, content_reference_id, claim_tag,
                              PENDING, None, None, "", None, self._clock.now(), None)
        self._records[record.id] = record
        return record

    def supersede_for(self, content_reference_id):
        for r in list(self._records.values()):
            if r.content_reference_id == content_reference_id and r.status != SUPERSEDED:
                self._records[r.id] = dataclasses.replace(r, status=SUPERSEDED)

    def get(self, review_id):
        if review_id not in self._records:
            raise NotFound(f"review {review_id}")
        return self._records[review_id]

    def list(self, project_id, status=None, node_id=None):
        return [r for r in self._records.values() if r.project_id == project_id
                and (status is None or r.status == status) and (node_id is None or r.node_id == node_id)]

    def blocking_for_node(self, node_id):
        return [r for r in self._records.values() if r.node_id == node_id and r.status in BLOCKING_STATUSES]

    def take_next(self, project_id, reviewer):
        self.expire_leases(self._lease)
        pending = self.list(project_id, PENDING)
        if not pending:
            return None
        record = dataclasses.replace(pending[0], status=TAKEN, reviewer=reviewer, taken_at=self._clock.now())
        self._records[record.id] = record
        text = self._references.get(record.content_reference_id, follow_superseded=False).text
        node = self._tree.get(record.node_id)
        resolved = []
        for c in citations_in(text):
            ref = self._references.get(c.reference_id, follow_superseded=False)
            lines = ref.text.splitlines()
            user = ref.origin in (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)
            resolved.append(ResolvedCitation(
                c, ref.origin, "\n".join(lines[c.start_line - 1:c.end_line]),
                "\n".join(lines[:c.start_line - 1]) if ref.origin == ORIGIN_USER_EXCHANGE else "",
                ref.text if user else ""))
        return ReviewPacket(record.id, node.title, node.context_summary, record.claim_tag, text, tuple(resolved))

    def submit(self, review_id, reviewer, verdict):
        record = self._held(review_id, reviewer)
        record = dataclasses.replace(record, status=PASSED if verdict.passed else FAILED, reason=verdict.reason,
                                     suggested_title=verdict.suggested_title, decided_at=self._clock.now())
        self._records[record.id] = record
        return record

    def release(self, review_id, reviewer):
        record = self._held(review_id, reviewer)
        self._records[record.id] = dataclasses.replace(record, status=PENDING, reviewer=None, taken_at=None)

    def expire_leases(self, older_than):
        cutoff = self._clock.now() - older_than
        expired = [r for r in self._records.values() if r.status == TAKEN and r.taken_at < cutoff]
        for r in expired:
            self._records[r.id] = dataclasses.replace(r, status=PENDING, reviewer=None, taken_at=None)
        return len(expired)

    def _held(self, review_id, reviewer):
        record = self.get(review_id)
        if record.status != TAKEN or record.reviewer != reviewer:
            raise Conflict(f"review {review_id} is {record.status} and not held by {reviewer}")
        return record
