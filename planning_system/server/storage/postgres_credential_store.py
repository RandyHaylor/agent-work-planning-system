"""postgres_credential_store: implements authentication's CredentialStoragePort. Declares credentials
(digests only, never plaintext; admin sessions are credentials of kind "admin_session") and
admin_password (one row).

set_admin_password_hash / has_admin_password are beyond the domain port: bootstrap needs to write
the hash and the port only reads it (gap reported; see bootstrap.ports.AdminPasswordStore).
"""
from __future__ import annotations

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, DateTime, Integer, Table, Text)
from sqlalchemy.engine import Connection

from planning_system.server.domain.authentication.ports import CredentialStoragePort

from .metadata import METADATA

CREDENTIALS = Table(
    "credentials", METADATA,
    Column("credential_id", Text, primary_key=True),
    Column("token_digest", Text, nullable=False, unique=True),
    Column("kind", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("agent_id", Text, nullable=True),
    Column("project_id", BigInteger, nullable=True),
    Column("scope_node_id", BigInteger, nullable=True),
    Column("minted_by", Text, nullable=True, index=True),
    Column("label", Text, nullable=True),
    Column("revoked", Boolean, nullable=False, default=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
)

ADMIN_PASSWORD = Table(
    "admin_password", METADATA,
    Column("id", Integer, primary_key=True),
    Column("password_hash", Text, nullable=False),
    CheckConstraint("id = 1", name="admin_password_single_row"),
)


class PostgresCredentialStore(CredentialStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def save(self, credential):
        raise NotImplementedError("level 7")

    def get(self, credential_id):
        raise NotImplementedError("level 7")

    def find_by_digest(self, token_digest):
        raise NotImplementedError("level 7")

    def minted_by(self, agent_id):
        raise NotImplementedError("level 7")

    def admin_password_hash(self):
        raise NotImplementedError("level 7")

    # beyond the port (bootstrap)
    def has_admin_password(self) -> bool:
        raise NotImplementedError("level 7")

    def set_admin_password_hash(self, password_hash: str) -> None:
        raise NotImplementedError("level 7")
