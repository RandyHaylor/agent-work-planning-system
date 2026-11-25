from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import httpx

DEFAULT_MAX_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class HttpFetchSettings:
    timeout_seconds: float = 15.0
    max_bytes: int = DEFAULT_MAX_BYTES
    user_agent: str = "planning-system-reader/0.1"
    follow_redirects: bool = True

    @classmethod
    def from_config(cls, config: Mapping) -> "HttpFetchSettings":
        """`config` is the "source_fetching" section."""
        raise NotImplementedError("level 7")


def build_http_client(settings: HttpFetchSettings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """httpx.Client with timeout, redirects and user agent from settings (`transport` for tests)."""
    raise NotImplementedError("level 7")
