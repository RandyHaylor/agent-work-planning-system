"""command: the Command base types. A command is data (its fields) + the permission it needs +
run(), which makes domain calls only (no HTTP, no SQL)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from planning_system.contract import Principal

from .permissions import Permission

if TYPE_CHECKING:
    from .services import Services


class Access(Enum):
    READ = "read"        # runs in a read-only transaction
    WRITE = "write"


class Command(ABC):
    access: Access

    @abstractmethod
    def required_permission(self) -> Permission:
        """Data only, e.g. CanReadNode(node_id); RequestAuthorizer resolves and checks it."""

    @abstractmethod
    def run(self, services: "Services", principal: Optional[Principal]) -> Any: ...


class ReadCommand(Command, ABC):
    access = Access.READ


class WriteCommand(Command, ABC):
    access = Access.WRITE


def hollow() -> Any:
    raise NotImplementedError("level 7")
