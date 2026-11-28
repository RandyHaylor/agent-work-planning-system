"""supersede (nested child of references): supersede candidates (05-spec-reference-supersede.md)."""
from .interface import SupersedeCandidates
from .ports import SupersedeCandidateStoragePort
from .supersede_candidates import SupersedeCandidateRegistry, candidate_kind
from .types import (CANDIDATE_STATUSES, CONFIRMED, FOUND_BY, FOUND_PROPOSED, FOUND_QUOTE_CHECK, FOUND_SAME_SOURCE,
                    KIND_DOCUMENT, KIND_USER_QUOTE, OPEN_STATUSES, PROPOSED, REJECTED, TRIAL_REVIEWED,
                    SupersedeCandidate)

__all__ = ["CANDIDATE_STATUSES", "CONFIRMED", "FOUND_BY", "FOUND_PROPOSED", "FOUND_QUOTE_CHECK", "FOUND_SAME_SOURCE",
           "KIND_DOCUMENT", "KIND_USER_QUOTE", "OPEN_STATUSES", "PROPOSED", "REJECTED", "SupersedeCandidate",
           "SupersedeCandidateRegistry", "SupersedeCandidateStoragePort", "SupersedeCandidates", "TRIAL_REVIEWED",
           "candidate_kind"]
