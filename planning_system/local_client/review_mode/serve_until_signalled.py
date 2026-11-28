"""serve_until_signalled: runs a review-mode loop in the foreground, registered in the client's running-sessions
registry so `planning halt` can find it.

Signals (build log #68): the first SIGINT/SIGTERM sets the stop event, so the review in hand finishes before the loop
returns; a second one aborts the review in progress at once (no more turns, nothing submitted). When the client is
halted (`planning halt` sets the marker before it signals), the first signal already aborts. An aborted review is not
released: its lease is left to expire (releasing is a server write, which a halted server refuses anyway), and the
reviewer process of the turn in flight is killed by the handle's cleanup."""
from __future__ import annotations

import logging
import signal
import threading
from contextlib import contextmanager, nullcontext
from typing import Callable, Iterator, Optional

from ..halt import ClientSessionTracker
from .interface import ReviewModeInterface

log = logging.getLogger(__name__)


class ReviewAborted(BaseException):
    """Raised in the main thread by the signal handler. BaseException so no `except Exception` (backends, the
    retry) swallows it."""


def run_review_mode(loop: ReviewModeInterface, once: bool, project_id: int = 0,
                    tracker: Optional[ClientSessionTracker] = None) -> dict:
    registration = tracker.review_loop(project_id) if tracker is not None else nullcontext()
    halted = tracker.is_halted if tracker is not None else (lambda: False)
    with registration:
        if once:
            return {"review_id": loop.run_once()}
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        stop = threading.Event()
        try:
            with _stop_on_signals(stop, halted):
                loop.serve(stop)
        except ReviewAborted:
            log.warning("review mode aborted: the review in progress was not submitted; its lease is left to expire")
            return {"stopped": True, "aborted": True}
    return {"stopped": True}


@contextmanager
def _stop_on_signals(stop: threading.Event, halted: Callable[[], bool]) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    signals = (signal.SIGINT, signal.SIGTERM)
    previous = {number: signal.getsignal(number) for number in signals}

    def handler(signum, frame) -> None:
        if stop.is_set() or halted():
            raise ReviewAborted()
        log.info("review mode: stopping after the review in hand (signal again to abort it)")
        stop.set()

    for number in signals:
        signal.signal(number, handler)
    try:
        yield
    finally:
        for number, previous_handler in previous.items():
            signal.signal(number, previous_handler)
