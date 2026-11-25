"""command_runner: permission check -> transaction (read-only for reads) -> run. Owns the transaction
(build log #13). Thin orchestration, real at level 6."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.storage.engine_setup import TransactionsInterface

from .command import Access, Command
from .request_authorizer import RequestAuthorizerInterface
from .services import ServicesFactory


class CommandRunnerInterface(ABC):
    @abstractmethod
    def run(self, command: Command, principal: Optional[Principal]) -> Any: ...


class CommandRunner(CommandRunnerInterface):
    def __init__(self, transactions: TransactionsInterface, stores_for, services_factory: ServicesFactory,
                 authorizer: RequestAuthorizerInterface):
        """stores_for: Storage.stores_for (connection -> Stores)."""
        self._transactions = transactions
        self._stores_for = stores_for
        self._services_factory = services_factory
        self._authorizer = authorizer

    def run(self, command, principal):
        opening = (self._transactions.read_only if command.access is Access.READ
                   else self._transactions.read_write)
        with opening() as conn:
            services = self._services_factory(self._stores_for(conn))
            self._authorizer.check(principal, command.required_permission(), services)
            return command.run(services, principal)
