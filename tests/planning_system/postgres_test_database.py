"""Test support: throwaway Postgres databases on the real container (planning_system_test_<random>),
created and dropped here. The server comes from PLANNING_TEST_SERVER_DSN (a dsn without a database
name), else from PLANNER_DB_PASSWORD / PLANNER_DB_PORT in the environment or the nearest .env.
Tests that need it skip when no server answers."""
from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from planning_system.configuration.environment_substitution import read_dotenv


def _dotenv() -> dict:
    for folder in Path(__file__).resolve().parents:
        if (folder / ".env").is_file():
            return read_dotenv(folder / ".env")
    return {}


def server_url() -> URL:
    explicit = os.environ.get("PLANNING_TEST_SERVER_DSN")
    if explicit:
        return make_url(explicit)
    values = {**_dotenv(), **os.environ}
    return URL.create("postgresql+psycopg", username=values.get("PLANNER_DB_USER", "planner"),
                      password=values.get("PLANNER_DB_PASSWORD"), host="127.0.0.1",
                      port=int(values.get("PLANNER_DB_PORT", 5433)))


def _admin_engine():
    return create_engine(server_url().set(database="postgres"), isolation_level="AUTOCOMMIT")


def new_database_url() -> URL:
    """A url for a database name that does not exist yet (skips the test when no server answers)."""
    engine = _admin_engine()
    try:
        with engine.connect():
            pass
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"no Postgres server for real tests: {error}")
    finally:
        engine.dispose()
    return server_url().set(database=f"planning_system_test_{secrets.token_hex(6)}")


def drop_database(url: URL) -> None:
    engine = _admin_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    finally:
        engine.dispose()


@contextmanager
def throwaway_database():
    """Creates an empty database, yields its url (password included), drops it afterwards."""
    url = new_database_url()
    engine = _admin_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        engine.dispose()
    try:
        yield url
    finally:
        drop_database(url)


def dsn(url: URL) -> str:
    return url.render_as_string(hide_password=False)
