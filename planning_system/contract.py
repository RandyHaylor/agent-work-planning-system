"""Shared contract every module builds against (fixed before parallel work).

See planning/BUILD-PLAN.md, "Shared contract".
"""
from dataclasses import dataclass, field
from typing import Optional

ROLES = ("admin", "planner", "worker", "quote_client")


@dataclass(frozen=True)
class Principal:
    """Who is acting. agent_id is a key into agent_registry (None for the quote key / plain admin).

    credential_id: the credential the request authenticated with (set by the authenticator; used to
    end one's own admin session). Not part of equality: the same principal is the same principal."""
    agent_id: Optional[str]
    role: str
    project_id: Optional[int] = None
    scope_node_id: Optional[int] = None
    credential_id: Optional[str] = field(default=None, compare=False)


class DomainError(Exception):
    """Base for errors http_api maps to HTTP status codes."""


class NotFound(DomainError):
    """-> 404"""


class Forbidden(DomainError):
    """-> 403"""


class Invalid(DomainError):
    """-> 422"""


class Conflict(DomainError):
    """-> 409 (e.g. a review verdict from someone not holding the review)"""
