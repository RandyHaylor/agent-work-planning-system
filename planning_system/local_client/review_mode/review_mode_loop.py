"""ReviewModeLoop: poll -> take -> backend -> submit (05-spec-citation-enforcement-and-review.md "Flow" 4).
One review at a time. Unparseable verdict or backend error: retry once, then release (a broken reviewer must not
fail someone's content)."""
from __future__ import annotations

import logging
from threading import Event
from typing import Optional

from planning_system.api_client import ApiError, PlanningApiClientInterface
from planning_system.errors import DomainError

from .interface import ReviewModeInterface
from .reviewer_backends.interface import ReviewerBackend
from .types import ReviewerUnavailable, ReviewPacket, UnparseableVerdict, Verdict

ATTEMPTS = 2

log = logging.getLogger(__name__)


class ReviewModeLoop(ReviewModeInterface):

    def __init__(self, api_client: PlanningApiClientInterface, backend: ReviewerBackend, project_id: int,
                 poll_seconds: float = 5.0):
        self._api = api_client
        self._backend = backend
        self._project_id = project_id
        self._poll_seconds = poll_seconds

    def run_once(self) -> Optional[str]:
        data = self._api.take_review(self._project_id)
        if not data:
            return None
        packet = ReviewPacket.from_json(data)
        verdict = self._review_with_one_retry(packet)
        if verdict is None:
            log.warning("review %s: no usable verdict after %d attempts; releasing", packet.review_id, ATTEMPTS)
            self._api.release_review(packet.review_id)
        else:
            self._api.submit_review_verdict(packet.review_id, verdict.passed, verdict.reason, verdict.suggested_title,
                                            verdict.findings)
            log.info("review %s: %s (%s)", packet.review_id, "passed" if verdict.passed else "failed", verdict.reason)
        return packet.review_id

    def serve(self, stop: Event) -> None:
        log.info("review mode: project %s, backend %s", self._project_id, self._backend.name)
        while not stop.is_set():
            try:
                handled = self.run_once()
            except (DomainError, ApiError) as error:       # server hiccup or lease lost: keep serving
                log.warning("review mode: server call failed: %s", error)
                handled = None
            if handled is None:
                stop.wait(self._poll_seconds)

    def _review_with_one_retry(self, packet: ReviewPacket) -> Optional[Verdict]:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                return self._backend.review(packet)
            except (ReviewerUnavailable, UnparseableVerdict) as error:
                log.warning("review %s attempt %d: %s: %s", packet.review_id, attempt, type(error).__name__, error)
        return None
