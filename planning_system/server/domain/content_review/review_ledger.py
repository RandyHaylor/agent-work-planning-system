"""ReviewLedgerService: the real ledger over ReviewStoragePort. take_next expires old leases, then takes
the oldest pending record row-locked (SKIP LOCKED in Postgres) inside the caller's transaction (the
CommandRunner owns it, build log #13)."""
from __future__ import annotations

import dataclasses
import uuid
from datetime import timedelta

from planning_system.errors import Conflict, NotFound

from .interface import ReviewLedger
from .ports import Clock, ReviewStoragePort
from .review_packet_builder import ReviewPacketBuilder
from .types import (BLOCKING_STATUSES, DEFAULT_LEASE, FAILED, PASSED, PENDING, STATUSES, SUPERSEDED, TAKEN,
                    ReviewRecord)


class ReviewLedgerService(ReviewLedger):
    def __init__(self, storage: ReviewStoragePort, references, tree, clock: Clock,
                 lease: timedelta = DEFAULT_LEASE):
        self._storage, self._clock, self._lease = storage, clock, lease
        self._packets = ReviewPacketBuilder(references, tree)

    def open(self, project_id, node_id, content_reference_id, claim_tag):
        record = ReviewRecord(id=f"rev-{uuid.uuid4()}", project_id=project_id, node_id=node_id,
                              content_reference_id=content_reference_id, claim_tag=claim_tag, status=PENDING,
                              reviewer=None, taken_at=None, reason="", suggested_title=None,
                              created_at=self._clock.now(), decided_at=None)
        self._storage.add(record)
        return record

    def supersede_for(self, content_reference_id):
        live = [s for s in STATUSES if s != SUPERSEDED]
        for record in self._storage.find(statuses=live, content_reference_id=content_reference_id):
            self._storage.save(dataclasses.replace(record, status=SUPERSEDED))

    def get(self, review_id):
        record = self._storage.get(review_id)
        if record is None:
            raise NotFound(f"review {review_id}")
        return record

    def list(self, project_id, status=None, node_id=None):
        return self._storage.find(project_id=project_id, statuses=None if status is None else (status,),
                                  node_id=node_id)

    def blocking_for_node(self, node_id):
        return self._storage.find(statuses=BLOCKING_STATUSES, node_id=node_id)

    def take_next(self, project_id, reviewer):
        self.expire_leases(self._lease)
        record = self._storage.lock_oldest_pending(project_id)
        if record is None:
            return None
        record = dataclasses.replace(record, status=TAKEN, reviewer=reviewer, taken_at=self._clock.now())
        self._storage.save(record)
        return self._packets.build(record)

    def submit(self, review_id, reviewer, verdict):
        record = dataclasses.replace(self._held(review_id, reviewer), status=PASSED if verdict.passed else FAILED,
                                     reason=verdict.reason, suggested_title=verdict.suggested_title,
                                     decided_at=self._clock.now())
        self._storage.save(record)
        return record

    def release(self, review_id, reviewer):
        record = self._held(review_id, reviewer)
        self._storage.save(dataclasses.replace(record, status=PENDING, reviewer=None, taken_at=None))

    def expire_leases(self, older_than):
        expired = self._storage.taken_before(self._clock.now() - older_than)
        for record in expired:
            self._storage.save(dataclasses.replace(record, status=PENDING, reviewer=None, taken_at=None))
        return len(expired)

    def _held(self, review_id, reviewer) -> ReviewRecord:
        record = self.get(review_id)
        if record.status != TAKEN or record.reviewer != reviewer:
            holder = f"held by {record.reviewer}" if record.status == TAKEN else "not taken"
            raise Conflict(f"review {review_id} is {record.status} ({holder}); only its holder may decide or "
                           "release it")
        return record
