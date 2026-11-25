"""Test support: transactions that record what was opened, and a Storage over the domain's
in-memory stores (one shared set; "rollback" is recorded, not undone)."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

from planning_system.server.domain.agent_registry.fakes import InMemoryAgentRegistryStorage
from planning_system.server.domain.authentication.fakes import InMemoryCredentialStorage
from planning_system.server.domain.project_tree.fakes import InMemoryTreeStorage
from planning_system.server.domain.references.fakes import (InMemoryReferenceStorage,
                                                            InMemoryTempCacheStorage)

from .engine_setup import TransactionsInterface
from .storage import Stores


@dataclass
class TransactionRecord:
    mode: str                       # "read_write" | "read_only"
    committed: bool = False
    rolled_back: bool = False
    error: BaseException | None = None


class RecordingTransactions(TransactionsInterface):
    """Yields a marker connection; records mode and whether the block ended cleanly."""

    def __init__(self):
        self.records: list[TransactionRecord] = []

    @contextmanager
    def _open(self, mode):
        record = TransactionRecord(mode)
        self.records.append(record)
        try:
            yield record
        except BaseException as error:
            record.rolled_back, record.error = True, error
            raise
        record.committed = True

    def read_write(self):
        return self._open("read_write")

    def read_only(self):
        return self._open("read_only")


def in_memory_stores() -> Stores:
    return Stores(tree=InMemoryTreeStorage(), references=InMemoryReferenceStorage(),
                  temp_cache=InMemoryTempCacheStorage(), credentials=InMemoryCredentialStorage(),
                  agent_registry=InMemoryAgentRegistryStorage())


@dataclass(frozen=True)
class InMemoryStorage:
    """Duck-types storage.Storage: same transactions attribute and stores_for(conn)."""
    transactions: RecordingTransactions = field(default_factory=RecordingTransactions)
    stores: Stores = field(default_factory=in_memory_stores)

    def stores_for(self, conn) -> Stores:
        return self.stores
