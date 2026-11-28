"""Storage: what the server composition gets. Stores: all five stores bound to one connection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from planning_system.configuration import ConfigSection
from planning_system.server.domain.agent_registry import AgentRegistryStoragePort
from planning_system.server.domain.authentication import CredentialStoragePort
from planning_system.server.domain.content_review import ReviewStoragePort
from planning_system.server.domain.project_tree import TreeStoragePort
from planning_system.server.domain.references import ReferenceStoragePort, TempCacheStoragePort

from alembic import command
from alembic.config import Config as AlembicConfig

from .engine_setup import Transactions, TransactionsInterface, create_engine_from_section
from .postgres_agent_registry_store import PostgresAgentRegistryStore
from .postgres_credential_store import PostgresCredentialStore
from .postgres_reference_store import PostgresReferenceStore
from .postgres_review_store import PostgresReviewStore
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
    reviews: ReviewStoragePort


@dataclass(frozen=True)
class Storage:
    transactions: TransactionsInterface

    def stores_for(self, conn) -> Stores:
        return Stores(tree=PostgresTreeStore(conn), references=PostgresReferenceStore(conn),
                      temp_cache=PostgresTempCacheStore(conn), credentials=PostgresCredentialStore(conn),
                      agent_registry=PostgresAgentRegistryStore(conn), reviews=PostgresReviewStore(conn))


def create_storage(section: ConfigSection) -> Storage:
    """Engine from the section -> Transactions -> Storage."""
    return Storage(Transactions(create_engine_from_section(section)))


def run_migrations(section: ConfigSection) -> None:
    """alembic upgrade head on the section's dsn (script_location = MIGRATIONS_DIR); used by bootstrap."""
    config = AlembicConfig()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", section.get("dsn").replace("%", "%%"))
    command.upgrade(config, "head")
