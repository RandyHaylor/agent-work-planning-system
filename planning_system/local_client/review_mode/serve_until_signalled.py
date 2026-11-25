"""serve_until_signalled: runs a review-mode loop in the foreground; SIGINT/SIGTERM (e.g. `planning task stop`
or Ctrl-C) set the stop event so the review in hand finishes before the loop returns."""
from __future__ import annotations

import logging
import signal
import threading
from contextlib import contextmanager
from typing import Iterator

from .interface import ReviewModeInterface


def run_review_mode(loop: ReviewModeInterface, once: bool) -> dict:
    if once:
        return {"review_id": loop.run_once()}
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stop = threading.Event()
    with _stop_on_signals(stop):
        loop.serve(stop)
    return {"stopped": True}


@contextmanager
def _stop_on_signals(stop: threading.Event) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    signals = (signal.SIGINT, signal.SIGTERM)
    previous = {number: signal.getsignal(number) for number in signals}
    for number in signals:
        signal.signal(number, lambda signum, frame: stop.set())
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
