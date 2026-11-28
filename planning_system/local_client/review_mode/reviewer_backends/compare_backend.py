"""CompareReviewerBackend: granularity `both` (build log #69). A content review runs once per method (per_sentence,
then bulk), each in its own fresh conversation (its own backend: for claude_code its own reviewer session); the
submitted verdict fails if either fails, and each run's reason is tagged with its method. Node, trial and quote-check
reviews have one method, so they run once (on the first backend). Disagreements are logged and handed to the
observer (the review log, build log #70).
User 2026-11-28: "Why can't we have a special test mode that runs both?"; "Fail if either fails (Recommended)"."""
from __future__ import annotations

import logging
from typing import Callable, Optional, Sequence

from ..types import KIND_CONTENT, ReviewPacket, Verdict
from .interface import ReviewerBackend

log = logging.getLogger(__name__)

# (verdict per method label, agreed) -> None
CompareObserver = Callable[[dict[str, Verdict], bool], None]


def merge_verdicts(verdicts: dict[str, Verdict]) -> Verdict:
    """Fails if any run failed; every run's reason tagged `[label]`; the first suggested title."""
    return Verdict(all(v.passed for v in verdicts.values()),
                   "; ".join(f"[{label}] {verdict.reason}" for label, verdict in verdicts.items()),
                   next((v.suggested_title for v in verdicts.values() if v.suggested_title), None))


class CompareReviewerBackend(ReviewerBackend):

    def __init__(self, runs: Sequence[tuple[str, ReviewerBackend]], observer: Optional[CompareObserver] = None):
        if len(runs) < 2:
            raise ValueError("compare mode needs at least two runs")
        self._runs = list(runs)
        self._observer = observer
        self.name = self._runs[0][1].name

    def observe_with(self, observer: CompareObserver) -> "CompareReviewerBackend":
        self._observer = observer
        return self

    def review(self, packet: ReviewPacket) -> Verdict:
        if packet.kind != KIND_CONTENT:
            return self._runs[0][1].review(packet)
        verdicts = {label: backend.review(packet) for label, backend in self._runs}
        agreed = len({verdict.passed for verdict in verdicts.values()}) == 1
        if not agreed:
            log.warning("review %s: methods disagree: %s", packet.review_id,
                        ", ".join(f"{label} {'passed' if v.passed else 'failed'}" for label, v in verdicts.items()))
        if self._observer is not None:
            self._observer(verdicts, agreed)
        return merge_verdicts(verdicts)
