"""SupersedeCandidateRegistry: the real SupersedeCandidates over its storage port and the ReferenceLibrary.
Nothing supersedes automatically (user 2026-11-27: "Why would a url reload auto supersede?"); confirm is the
one call that supersedes."""
from __future__ import annotations

import dataclasses
import uuid

from planning_system.errors import Conflict, Invalid, NotFound

from ..interface import ReferenceLibrary
from ..ports import Clock
from ..types import ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE, ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE
from .interface import SupersedeCandidates
from .ports import SupersedeCandidateStoragePort
from .types import (CONFIRMED, KIND_DOCUMENT, KIND_USER_QUOTE, OPEN_STATUSES, PROPOSED, REJECTED,
                    TRIAL_REVIEWED, SupersedeCandidate)

KIND_BY_ORIGIN = {ORIGIN_DOCUMENT: KIND_DOCUMENT, ORIGIN_KNOWLEDGE_BASE: KIND_DOCUMENT,
                  ORIGIN_USER_EXCHANGE: KIND_USER_QUOTE, ORIGIN_PROPOSAL_RESPONSE: KIND_USER_QUOTE}


def candidate_kind(old_origin: str, new_origin: str) -> str:
    old_kind, new_kind = KIND_BY_ORIGIN.get(old_origin), KIND_BY_ORIGIN.get(new_origin)
    if old_kind is None or new_kind is None:
        raise Invalid(f"only evidence can be superseded (user quotes, documents); got {old_origin} -> {new_origin}")
    if old_kind != new_kind:
        raise Invalid(f"a {old_origin} reference can only be superseded by the same kind of evidence, "
                      f"not {new_origin}")
    return old_kind


class SupersedeCandidateRegistry(SupersedeCandidates):

    def __init__(self, storage: SupersedeCandidateStoragePort, library: ReferenceLibrary, clock: Clock):
        self._storage, self._library, self._clock = storage, library, clock

    def propose(self, project_id, old_reference_id, new_reference_id, found_by, proposed_by, reason=""):
        if old_reference_id == new_reference_id:
            raise Invalid("a reference can't supersede itself")
        existing = self._storage.find(project_id=project_id, old_reference_id=old_reference_id,
                                      new_reference_id=new_reference_id)
        if existing:
            return existing[0], False
        old = self._library.get(old_reference_id, follow_superseded=False)
        new = self._library.get(new_reference_id, follow_superseded=False)
        if old.superseded_by:
            raise Invalid(f"{old.id} is already superseded by {old.superseded_by}")
        candidate = SupersedeCandidate(f"sup-{uuid.uuid4()}", project_id, old.id, new.id,
                                       candidate_kind(old.origin, new.origin), found_by, PROPOSED, proposed_by,
                                       reason, self._clock.now())
        self._storage.add(candidate)
        return candidate, True

    def get(self, candidate_id):
        candidate = self._storage.get(candidate_id)
        if candidate is None:
            raise NotFound(f"supersede candidate {candidate_id}")
        return candidate

    def list(self, project_id, status=None):
        return self._storage.find(project_id=project_id, status=status)

    def mark_trial_reviewed(self, candidate_id, request_node_id):
        candidate = dataclasses.replace(self._open(candidate_id), status=TRIAL_REVIEWED,
                                        request_node_id=request_node_id)
        self._storage.save(candidate)
        return candidate

    def confirm(self, candidate_id, decided_by):
        candidate = self._open(candidate_id)
        self._library.supersede(candidate.old_reference_id, candidate.new_reference_id)
        return self._decide(candidate, CONFIRMED, decided_by, candidate.reason)

    def reject(self, candidate_id, decided_by, reason):
        return self._decide(self._open(candidate_id), REJECTED, decided_by, reason)

    def _open(self, candidate_id) -> SupersedeCandidate:
        candidate = self.get(candidate_id)
        if candidate.status not in OPEN_STATUSES:
            raise Conflict(f"supersede candidate {candidate_id} is already {candidate.status}")
        return candidate

    def _decide(self, candidate, status, decided_by, reason) -> SupersedeCandidate:
        decided = dataclasses.replace(candidate, status=status, decided_by=decided_by, reason=reason,
                                      decided_at=self._clock.now())
        self._storage.save(decided)
        return decided
