"""engine_setup: Engine from the storage config section; Transactions (read-write / read-only).

`with engine.begin()` is the unit of work (recorded decision); nothing homemade.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from sqlalchemy.engine import Connection, Engine

from planning_system.configuration import ConfigSection


class TransactionsInterface(ABC):
    @abstractmethod
    def read_write(self) -> AbstractContextManager[Connection]:
        """engine.begin(): commit on success, roll back when the block raises."""

    @abstractmethod
    def read_only(self) -> AbstractContextManager[Connection]:
        """engine.begin() + SET TRANSACTION READ ONLY."""


class Transactions(TransactionsInterface):
    def __init__(self, engine: Engine):
        self._engine = engine

    def read_write(self):
        raise NotImplementedError("level 7")

    def read_only(self):
        raise NotImplementedError("level 7")


def create_engine_from_section(section: ConfigSection) -> Engine:
    """Keys: dsn (postgresql+psycopg://...), pool_size. Nobody else interprets them."""
    raise NotImplementedError("level 7")
