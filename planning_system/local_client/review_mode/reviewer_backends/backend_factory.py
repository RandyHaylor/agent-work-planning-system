"""ReviewerBackendFactory: backend name (from client config / `--backend`) -> backend. Adding a harness = one class
plus one entry here."""
from __future__ import annotations

from typing import Callable, Optional

import httpx

from ...review_worker import ReviewWorkerInterface
from .interface import ReviewerBackend

DEFAULT_BACKEND = "local_llm"
BACKEND_NAMES = ("local_llm", "claude_code", "pi")

ReviewWorkerFactory = Callable[[str], ReviewWorkerInterface]   # model name -> review worker


class ReviewerBackendFactory:

    def __init__(self, review_worker_factory: Optional[ReviewWorkerFactory] = None,
                 http_transport: Optional[httpx.BaseTransport] = None):
        self._review_worker_factory = review_worker_factory
        self._http_transport = http_transport

    def create(self, name: Optional[str] = None, model: Optional[str] = None) -> ReviewerBackend:
        raise NotImplementedError
