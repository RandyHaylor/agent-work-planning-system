"""LoggingReviewerBackend: ReviewerBackend decorator; one review log record per review attempt, whether it ends in a
verdict, an unparseable answer, a backend failure, a halt or an abort. A log write that fails never fails the
review."""
from __future__ import annotations

import logging
from typing import Optional

from ..reviewer_backends.interface import ReviewerBackend
from ..types import ReviewerIdentity, ReviewPacket, Verdict
from .review_log_file import ReviewLogFile
from .review_recorder import ReviewRecorder

log = logging.getLogger(__name__)


class LoggingReviewerBackend(ReviewerBackend):

    def __init__(self, inner: ReviewerBackend, recorder: ReviewRecorder, log_file: ReviewLogFile,
                 identity: Optional[ReviewerIdentity], project_id: int):
        self._inner = inner
        self._recorder = recorder
        self._log_file = log_file
        self._project_id = project_id
        self.identity = identity
        self.name = inner.name

    def review(self, packet: ReviewPacket) -> Verdict:
        self._recorder.begin(packet, self._project_id, self.identity)
        try:
            verdict = self._inner.review(packet)
        except BaseException as error:
            self._write(self._recorder.finish(error=error))
            raise
        self._write(self._recorder.finish(verdict=verdict))
        return verdict

    def _write(self, record: dict) -> None:
        try:
            self._log_file.append(record)
        except OSError as error:
            log.warning("review %s: could not write the review log: %s", record.get("review_id"), error)
