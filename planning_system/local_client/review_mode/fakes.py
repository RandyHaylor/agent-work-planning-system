"""FakeReviewModeLoop: minimal working loop (no logging, no API-error tolerance)."""
from __future__ import annotations

from threading import Event
from typing import Optional

from planning_system.api_client import PlanningApiClientInterface

from .interface import ReviewModeInterface
from .reviewer_backends.interface import ReviewerBackend
from .types import ReviewerUnavailable, ReviewPacket, UnparseableVerdict


class FakeReviewModeLoop(ReviewModeInterface):

    def __init__(self, api_client: PlanningApiClientInterface, backend: ReviewerBackend, project_id: int,
                 poll_seconds: float = 5.0):
        self._api, self._backend, self._project_id, self._poll = api_client, backend, project_id, poll_seconds

    def run_once(self) -> Optional[str]:
        data = self._api.take_review(self._project_id)
        if not data:
            return None
        packet = ReviewPacket.from_json(data)
        for _ in range(2):
            try:
                verdict = self._backend.review(packet)
            except (ReviewerUnavailable, UnparseableVerdict):
                continue
            self._api.submit_review_verdict(packet.review_id, verdict.passed, verdict.reason, verdict.suggested_title,
                                            verdict.findings)
            return packet.review_id
        self._api.release_review(packet.review_id)
        return packet.review_id

    def serve(self, stop: Event) -> None:
        while not stop.is_set():
            if self.run_once() is None:
                stop.wait(self._poll)
