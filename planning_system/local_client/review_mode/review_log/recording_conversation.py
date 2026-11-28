"""RecordingConversation: ReviewConversation decorator; every turn sent, the raw answer (or the failure), the answer's
JSON as parsed, and the turn's time go into the run it was given. Methods and backends do not change."""
from __future__ import annotations

import time
from typing import Optional

from ..review_conversation import ReviewConversation
from ..verdict_parser import find_json_object


class RecordingConversation(ReviewConversation):

    def __init__(self, inner: ReviewConversation, run: dict):
        self._inner = inner
        self._run = run

    def say(self, text: str, max_tokens: Optional[int] = None) -> str:
        turn: dict = {"sent": text}
        self._run["turns"].append(turn)
        started = time.monotonic()
        try:
            answer = self._inner.say(text, max_tokens) if max_tokens is not None else self._inner.say(text)
        except BaseException as error:           # backend failure, halt, abort: logged, then passed on
            turn.update(error=f"{type(error).__name__}: {error}", seconds=_since(started))
            raise
        turn.update(answer=answer, parsed=find_json_object(answer, lambda data: True), seconds=_since(started))
        return answer


def _since(started: float) -> float:
    return round(time.monotonic() - started, 3)
