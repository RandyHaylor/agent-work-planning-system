"""ReviewModeLoop: poll -> take -> backend -> submit (05-spec-citation-enforcement-and-review.md "Flow" 4)."""
from __future__ import annotations

from threading import Event
from typing import Optional

from planning_system.api_client import PlanningApiClientInterface

from .interface import ReviewModeInterface
from .reviewer_backends.interface import ReviewerBackend


class ReviewModeLoop(ReviewModeInterface):

    def __init__(self, api_client: PlanningApiClientInterface, backend: ReviewerBackend, project_id: int,
                 poll_seconds: float = 5.0):
        self._api = api_client
        self._backend = backend
        self._project_id = project_id
        self._poll_seconds = poll_seconds

    def run_once(self) -> Optional[str]:
        raise NotImplementedError

    def serve(self, stop: Event) -> None:
        raise NotImplementedError
