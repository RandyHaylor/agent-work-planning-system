"""Private: one httpx.Client (base URL, Bearer header, TLS verify, JSON in/out, status -> contract errors).

Level 6 scaffold: hollow. Level 7 fills it.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from .types import ClientSettings


class HttpTransport:
    """status 404 -> NotFound, 403 -> Forbidden, 422 -> Invalid, other failure -> ApiError.
    Never logs or puts the token into an error."""

    def __init__(self, settings: ClientSettings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._transport = transport

    def request(self, method: str, path: str, *, json: Any = None,
                params: Optional[dict] = None) -> Any:
        raise NotImplementedError("level 7")
