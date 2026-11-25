"""ReviewLedgerService: the real ledger over ReviewStoragePort; lease expiry at the start of each take."""
from __future__ import annotations

from datetime import timedelta

from .interface import ReviewLedger
from .ports import Clock, ReviewStoragePort
from .types import DEFAULT_LEASE


class ReviewLedgerService(ReviewLedger):
    def __init__(self, storage: ReviewStoragePort, references, tree, clock: Clock,
                 lease: timedelta = DEFAULT_LEASE):
        self._storage, self._references, self._tree, self._clock = storage, references, tree, clock
        self._lease = lease

    def open(self, project_id, node_id, content_reference_id, claim_tag):
        raise NotImplementedError("level 7")

    def supersede_for(self, content_reference_id):
        raise NotImplementedError("level 7")

    def get(self, review_id):
        raise NotImplementedError("level 7")

    def list(self, project_id, status=None, node_id=None):
        raise NotImplementedError("level 7")

    def blocking_for_node(self, node_id):
        raise NotImplementedError("level 7")

    def take_next(self, project_id, reviewer):
        raise NotImplementedError("level 7")

    def submit(self, review_id, reviewer, verdict):
        raise NotImplementedError("level 7")

    def release(self, review_id, reviewer):
        raise NotImplementedError("level 7")

    def expire_leases(self, older_than):
        raise NotImplementedError("level 7")
