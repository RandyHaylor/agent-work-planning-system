"""api_client types (spec: planning/05-spec-api-client.md)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

DEFAULT_BASE_URL = "https://127.0.0.1:8443"

ENV_URL = "PLANNING_URL"
ENV_CA_CERT = "PLANNING_CA_CERT"
ENV_TOKEN = "PLANNING_TOKEN"


@dataclass(frozen=True)
class ClientSettings:
    base_url: str = DEFAULT_BASE_URL
    ca_cert_path: Optional[Path] = None   # the server's self-signed cert; None = system trust
    token: Optional[str] = None
    timeout_seconds: float = 30

    def __repr__(self) -> str:  # never show the token
        return (f"ClientSettings(base_url={self.base_url!r}, ca_cert_path={self.ca_cert_path!r}, "
                f"token={'<set>' if self.token else None}, timeout_seconds={self.timeout_seconds})")


class ApiError(Exception):
    """Unexpected status from the server; carries status + body (never the token)."""

    def __init__(self, status: int, body: Union[dict, str]):
        super().__init__(f"server returned {status}: {body}")
        self.status = status
        self.body = body
