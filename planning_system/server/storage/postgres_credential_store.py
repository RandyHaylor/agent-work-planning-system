"""postgres_credential_store: implements authentication's CredentialStoragePort. Declares credentials
(digests only, never plaintext; admin sessions are credentials of kind "admin_session") and
admin_password (one row).

set_admin_password_hash / has_admin_password are beyond the domain port: bootstrap needs to write
the hash and the port only reads it (gap reported; see bootstrap.ports.AdminPasswordStore).
"""
from __future__ import annotations

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, DateTime, Integer, Table, Text)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from planning_system.contract import Forbidden, Principal
from planning_system.server.domain.authentication import CredentialStoragePort
from planning_system.server.domain.authentication import StoredCredential

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
        p = credential.principal
        row = dict(credential_id=credential.credential_id, token_digest=credential.token_digest,
                   kind=credential.kind, role=p.role, agent_id=p.agent_id, project_id=p.project_id,
                   scope_node_id=p.scope_node_id, minted_by=credential.minted_by, label=credential.label,
                   revoked=credential.revoked, expires_at=credential.expires_at)
        statement = insert(CREDENTIALS).values(**row)
        self._conn.execute(statement.on_conflict_do_update(
            index_elements=[CREDENTIALS.c.credential_id],
            set_={k: statement.excluded[k] for k in row if k != "credential_id"}))

    def get(self, credential_id):
        found = self._credentials(select(CREDENTIALS).where(CREDENTIALS.c.credential_id == credential_id))
        return found[0] if found else None

    def find_by_digest(self, token_digest):
        found = self._credentials(select(CREDENTIALS).where(CREDENTIALS.c.token_digest == token_digest))
        return found[0] if found else None

    def minted_by(self, agent_id):
        return self._credentials(select(CREDENTIALS).where(CREDENTIALS.c.minted_by == agent_id)
                                 .order_by(CREDENTIALS.c.credential_id))

    def admin_password_hash(self):
        password_hash = self._conn.execute(select(ADMIN_PASSWORD.c.password_hash)).scalar_one_or_none()
        if password_hash is None:
            raise Forbidden("no admin password set: run `planning-server bootstrap` first")
        return password_hash

    # beyond the port (bootstrap)
    def has_admin_password(self) -> bool:
        return self._conn.execute(select(ADMIN_PASSWORD.c.id)).first() is not None

    def set_admin_password_hash(self, password_hash: str) -> None:
        statement = insert(ADMIN_PASSWORD).values(id=1, password_hash=password_hash)
        self._conn.execute(statement.on_conflict_do_update(
            index_elements=[ADMIN_PASSWORD.c.id], set_={"password_hash": statement.excluded.password_hash}))

    def _credentials(self, statement):
        return [StoredCredential(r.credential_id, r.token_digest,
                                 Principal(r.agent_id, r.role, r.project_id, r.scope_node_id), r.kind,
                                 r.minted_by, r.label, r.revoked, r.expires_at)
                for r in self._conn.execute(statement)]
