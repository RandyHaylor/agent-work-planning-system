"""FastAPI dependencies every module router uses. Signatures are the contract;
worktree A (core server) fills in the bodies. Other modules import these names only.

- current_principal: reads the Bearer token, returns a Principal (raises Forbidden if unknown).
- db_connection: yields a SQLAlchemy Connection inside one transaction per request
  (commit on success, rollback on error).
"""
from typing import Iterator

from sqlalchemy.engine import Connection

from planning_system.contract import Principal


def current_principal() -> Principal:  # replaced by worktree A
    raise NotImplementedError


def db_connection() -> Iterator[Connection]:  # replaced by worktree A
    raise NotImplementedError
    yield  # pragma: no cover
