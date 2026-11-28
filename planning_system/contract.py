"""Shared contract every module builds against (fixed before parallel work).

See planning/BUILD-PLAN.md, "Shared contract". The error family lives in planning_system/errors.py
(re-exported here so existing imports keep working).
"""
from dataclasses import dataclass, field
from typing import Optional

from planning_system.errors import Conflict, DomainError, Forbidden, Halted, Invalid, NotFound

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


__all__ = ["Conflict", "DomainError", "Forbidden", "Halted", "Invalid", "NotFound", "Principal", "ROLES"]
