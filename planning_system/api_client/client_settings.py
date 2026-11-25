"""client_settings: builds ClientSettings from the environment and decides TLS verification."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Union
from urllib.parse import urlparse

from .types import DEFAULT_BASE_URL, ENV_CA_CERT, ENV_TOKEN, ENV_URL, ClientSettings

_LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def settings_from_environment(environment: Mapping[str, str]) -> ClientSettings:
    """PLANNING_URL, PLANNING_CA_CERT, PLANNING_TOKEN -> ClientSettings."""
    ca_cert = environment.get(ENV_CA_CERT)
    return ClientSettings(
        base_url=environment.get(ENV_URL) or DEFAULT_BASE_URL,
        ca_cert_path=Path(ca_cert) if ca_cert else None,
        token=environment.get(ENV_TOKEN) or None,
    )


def tls_verify_for(settings: ClientSettings) -> Union[str, bool]:
    """CA path if set; False only when unset and the URL is localhost; otherwise True."""
    if settings.ca_cert_path is not None:
        return str(settings.ca_cert_path)
    return urlparse(settings.base_url).hostname not in _LOCAL_HOSTS
