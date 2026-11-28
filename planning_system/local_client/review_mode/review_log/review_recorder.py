"""ReviewRecorder: builds one review log record per review attempt. The logging backend opens and closes the record;
the recording conversations add one run per conversation (labelled with its method) and its turns; compare mode
reports both verdicts and whether they agreed."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from ..review_conversation import ReviewConversation
from ..sentence_splitter import SentenceSplitter
from ..types import KIND_CONTENT, ReviewerIdentity, ReviewPacket, Verdict
from .recording_conversation import RecordingConversation


class ReviewRecorder:

    def __init__(self, splitter: Optional[SentenceSplitter] = None):
        self._splitter = splitter or SentenceSplitter()
        self._record: Optional[dict] = None
        self._started = 0.0

    def begin(self, packet: ReviewPacket, project_id: int, identity: Optional[ReviewerIdentity]) -> None:
        self._started = time.monotonic()
        self._record = {
            "logged_at": datetime.now(timezone.utc).isoformat(), "review_id": packet.review_id,
            "kind": packet.kind, "project_id": project_id, **(identity.as_dict() if identity else {}),
            "claim_tag": packet.claim_tag,
            "sentences": self._splitter.split(packet.claim_text) if packet.kind == KIND_CONTENT else [],
            "runs": [], "verdict": None, "error": None}

    def conversation(self, inner: ReviewConversation, label: str) -> ReviewConversation:
        """A new run for this conversation; passes the conversation through when no review is being recorded."""
        if self._record is None:
            return inner
        run = {"method": label, "turns": [], "verdict": None}
        self._record["runs"].append(run)
        return RecordingConversation(inner, run)

    def compared(self, verdicts: dict[str, Verdict], agreed: bool) -> None:
        if self._record is None:
            return
        for run in self._record["runs"]:
            if run["method"] in verdicts:
                run["verdict"] = _verdict(verdicts[run["method"]])
        self._record["compare"] = {"agreed": agreed,
                                   "passed": {label: verdict.passed for label, verdict in verdicts.items()}}

    def finish(self, verdict: Optional[Verdict] = None, error: Optional[BaseException] = None) -> dict:
        record, self._record = self._record or {}, None
        record["verdict"] = _verdict(verdict) if verdict is not None else None
        record["error"] = f"{type(error).__name__}: {error}" if error is not None else None
        runs = record.get("runs", [])
        if len(runs) == 1 and runs[0]["verdict"] is None:
            runs[0]["verdict"] = record["verdict"]
        record["model_calls"] = sum(len(run["turns"]) for run in runs)
        record["total_seconds"] = round(time.monotonic() - self._started, 3)
        return record


def _verdict(verdict: Verdict) -> dict:
    return {"passed": verdict.passed, "reason": verdict.reason, "suggested_title": verdict.suggested_title,
            "findings": list(verdict.findings)}
