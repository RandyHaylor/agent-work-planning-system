"""Private: one httpx.Client (base URL, Bearer header, TLS verify, JSON in/out, status -> contract errors)."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from planning_system.contract import Forbidden, Invalid, NotFound

from .client_settings import tls_verify_for
from .types import ApiError, ClientSettings

_CONTRACT_ERRORS = {404: NotFound, 403: Forbidden, 422: Invalid}


class HttpTransport:
    """status 404 -> NotFound, 403 -> Forbidden, 422 -> Invalid, other failure -> ApiError.
    Never logs or puts the token into an error."""

    def __init__(self, settings: ClientSettings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._transport = transport

    @property
    def settings(self) -> ClientSettings:
        return self._settings

    @property
    def raw_transport(self) -> Optional[httpx.BaseTransport]:
        return self._transport

    def request(self, method: str, path: str, *, json: Any = None,
                params: Optional[dict] = None) -> Any:
        headers = {"Authorization": f"Bearer {self._settings.token}"} if self._settings.token else {}
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        with httpx.Client(base_url=self._settings.base_url, transport=self._transport,
                          verify=tls_verify_for(self._settings),
                          timeout=self._settings.timeout_seconds) as client:
            response = client.request(method, path, json=json, params=clean_params, headers=headers)
        return self._decode(response)

    def _decode(self, response: httpx.Response) -> Any:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.is_success:
            return body
        token = self._settings.token
        if token and isinstance(body, str):
            body = body.replace(token, "<token>")
        error_type = _CONTRACT_ERRORS.get(response.status_code)
        if error_type is not None:
            detail = body.get("detail", body) if isinstance(body, dict) else body
            message = str(detail)
            if token:
                message = message.replace(token, "<token>")
            raise error_type(message)
        raise ApiError(response.status_code, body)
