"""credential_dependency: Bearer header -> CredentialAuthenticator.authenticate -> Principal.
Missing or unknown token -> Forbidden (403). No server-wide access header exists."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Header

from planning_system.contract import Forbidden, Principal
from planning_system.server.domain.authentication import CredentialAuthenticator


def bearer_token(authorization: Optional[str] = Header(default=None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Forbidden("missing Bearer token")
    return token.strip()


def principal_dependency(authenticator: CredentialAuthenticator) -> Callable[..., Principal]:
    """The function installed in place of dependencies.current_principal."""

    def current_principal(authorization: Optional[str] = Header(default=None)) -> Principal:
        return authenticator.authenticate(bearer_token(authorization))

    return current_principal
