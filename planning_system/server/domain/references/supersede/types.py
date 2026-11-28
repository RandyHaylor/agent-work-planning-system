"""Types for supersede candidates (05-spec-reference-supersede.md, approved): a pair "new may supersede old",
never applied automatically; kept with its reason when rejected."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

PROPOSED, TRIAL_REVIEWED, CONFIRMED, REJECTED = "proposed", "trial_reviewed", "confirmed", "rejected"
CANDIDATE_STATUSES = (PROPOSED, TRIAL_REVIEWED, CONFIRMED, REJECTED)
OPEN_STATUSES = (PROPOSED, TRIAL_REVIEWED)

KIND_DOCUMENT = "document"        # the planner may confirm (the user may override)
KIND_USER_QUOTE = "user_quote"    # only the user (admin) confirms

FOUND_SAME_SOURCE = "same_source"      # the same URL or file loaded again with different content
FOUND_QUOTE_CHECK = "quote_check"      # the all-quotes check said the new user quote changes the old one
FOUND_PROPOSED = "proposed"            # `planning references propose-supersede OLD NEW`
FOUND_BY = (FOUND_SAME_SOURCE, FOUND_QUOTE_CHECK, FOUND_PROPOSED)


@dataclass(frozen=True)
class SupersedeCandidate:
    id: str                          # "sup-<uuid4>"
    project_id: int
    old_reference_id: str
    new_reference_id: str
    kind: str                        # KIND_DOCUMENT | KIND_USER_QUOTE
    found_by: str
    status: str
    proposed_by: Optional[str]       # agent id, "admin", or None (found by the server)
    reason: str                      # why it was proposed; on reject, why not
    created_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    request_node_id: Optional[int] = None    # the requirement request task that asks to confirm it
