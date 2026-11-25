"""Storage: what the server composition gets. Stores: all five stores bound to one connection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from planning_system.configuration import ConfigSection
from planning_system.server.domain.agent_registry.ports import AgentRegistryStoragePort
from planning_system.server.domain.authentication.ports import CredentialStoragePort
from planning_system.server.domain.project_tree.ports import TreeStoragePort
from planning_system.server.domain.references.ports import ReferenceStoragePort, TempCacheStoragePort

from .engine_setup import TransactionsInterface
from .postgres_agent_registry_store import PostgresAgentRegistryStore
from .postgres_credential_store import PostgresCredentialStore
from .postgres_reference_store import PostgresReferenceStore
from .postgres_temp_cache_store import PostgresTempCacheStore
from .postgres_tree_store import PostgresTreeStore

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


@dataclass(frozen=True)
class Stores:
    tree: TreeStoragePort
    references: ReferenceStoragePort
    temp_cache: TempCacheStoragePort
    credentials: CredentialStoragePort
    agent_registry: AgentRegistryStoragePort


@dataclass(frozen=True)
class Storage:
    transactions: TransactionsInterface

    def stores_for(self, conn) -> Stores:
        return Stores(tree=PostgresTreeStore(conn), references=PostgresReferenceStore(conn),
                      temp_cache=PostgresTempCacheStore(conn), credentials=PostgresCredentialStore(conn),
                      agent_registry=PostgresAgentRegistryStore(conn))


def create_storage(section: ConfigSection) -> Storage:
    """Engine from the section -> Transactions -> Storage."""
    raise NotImplementedError("level 7")


def run_migrations(section: ConfigSection) -> None:
    """alembic upgrade head on the section's dsn (script_location = MIGRATIONS_DIR); used by bootstrap."""
    raise NotImplementedError("level 7")
