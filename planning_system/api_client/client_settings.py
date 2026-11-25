"""client_settings: builds ClientSettings from the environment and decides TLS verification.

Level 6 scaffold: hollow.
"""
from __future__ import annotations

from typing import Mapping, Union

from .types import ClientSettings


def settings_from_environment(environment: Mapping[str, str]) -> ClientSettings:
    """PLANNING_URL, PLANNING_CA_CERT, PLANNING_TOKEN -> ClientSettings."""
    raise NotImplementedError("level 7")


def tls_verify_for(settings: ClientSettings) -> Union[str, bool]:
    """CA path if set; False only when unset and the URL is localhost; otherwise True."""
    raise NotImplementedError("level 7")
