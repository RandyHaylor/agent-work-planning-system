"""request_authorizer: resolves the facts a permission needs (node, ancestors, citing nodes, temp entry)
through the domain, asks access/PermissionPolicy, raises Forbidden."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from planning_system.contract import Principal

from .permissions import Permission
from .services import Services


class RequestAuthorizerInterface(ABC):
    @abstractmethod
    def check(self, principal: Optional[Principal], permission: Permission, services: Services) -> None:
        """Returns, or raises Forbidden (NotFound when a named node/reference doesn't exist).
        principal None passes only NoPrincipalNeeded."""


class RequestAuthorizer(RequestAuthorizerInterface):
    def check(self, principal, permission, services):
        raise NotImplementedError("level 7")
