"""Real Postgres for the storage contract: one migrated throwaway database per session; each test
gets a connection inside a transaction that is rolled back."""
import pytest
from sqlalchemy import create_engine

from planning_system.configuration import ConfigSection
from planning_system.server.storage import run_migrations
from tests.planning_system.postgres_test_database import dsn, throwaway_database


@pytest.fixture(scope="session")
def migrated_dsn():
    with throwaway_database() as url:
        run_migrations(ConfigSection("storage", {"dsn": dsn(url)}))
        yield dsn(url)


@pytest.fixture(scope="session")
def engine(migrated_dsn):
    engine = create_engine(migrated_dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine):
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()
