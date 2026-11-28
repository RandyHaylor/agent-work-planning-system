"""Test support: in-memory storage, a settable clock, and a fake implementing all three interfaces."""
import dataclasses
import hashlib
import itertools
import secrets
from datetime import datetime, timedelta, timezone

from planning_system.contract import Forbidden, NotFound, Principal
from planning_system.server.domain.access import CredentialScope

from .interface import AdminSessions, CredentialAuthenticator, CredentialIssuer
from .ports import Clock, CredentialStoragePort
from .types import (KIND_ADMIN_SESSION, KIND_AGENT, KIND_QUOTE_KEY, IssuedCredential,
                    StoredCredential)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class FakeClock(Clock):
    def __init__(self, start: datetime | None = None):
        self.current = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self):
        return self.current

    def advance(self, delta: timedelta):
        self.current += delta


class InMemoryCredentialStorage(CredentialStoragePort):
    def __init__(self, admin_password: str = "admin-pw"):
        self.rows: dict[str, StoredCredential] = {}
        self._admin_hash = _sha(admin_password)   # fake hash; real uses PBKDF2

    def save(self, credential):
        self.rows[credential.credential_id] = credential

    def get(self, credential_id):
        return self.rows.get(credential_id)

    def find_by_digest(self, token_digest):
        return next((c for c in self.rows.values() if c.token_digest == token_digest), None)

    def minted_by(self, agent_id):
        return [c for c in self.rows.values() if agent_id is not None and c.minted_by == agent_id]

    def admin_password_hash(self):
        return self._admin_hash


class FakeAuthentication(CredentialAuthenticator, CredentialIssuer, AdminSessions):
    _ids = itertools.count(1)

    def __init__(self, storage, policy, clock, ttl: timedelta = timedelta(hours=8)):
        self._storage, self._policy, self._clock, self._ttl = storage, policy, clock, ttl

    # helpers
    def _issue(self, principal, kind, minted_by=None, label=None, expires_at=None):
        token = secrets.token_urlsafe(16)
        cid = f"cred-{next(self._ids)}"
        self._storage.save(StoredCredential(cid, _sha(token), principal, kind, minted_by, label,
                                            False, expires_at))
        return IssuedCredential(token, cid, principal)

    def _require(self, credential_id):
        row = self._storage.get(credential_id)
        if row is None:
            raise NotFound(credential_id)
        return row

    @staticmethod
    def _scope(row):
        p = row.principal
        return CredentialScope(p.role, p.project_id, p.scope_node_id)

    # CredentialAuthenticator
    def authenticate(self, presented_token):
        row = self._storage.find_by_digest(_sha(presented_token))
        if row is None or row.revoked:
            raise Forbidden("unknown or revoked credential")
        if row.expires_at is not None and self._clock.now() >= row.expires_at:
            raise Forbidden("expired credential")
        return dataclasses.replace(row.principal, credential_id=row.credential_id)

    def credential_scope(self, credential_id):
        return self._scope(self._require(credential_id))

    # CredentialIssuer
    def mint(self, issuer, role, project_id, scope_node_id, agent_id):
        if not self._policy.can_mint(issuer, CredentialScope(role, project_id, scope_node_id), role):
            raise Forbidden("may not mint")
        return self._issue(Principal(agent_id, role, project_id, scope_node_id), KIND_AGENT,
                           minted_by=issuer.agent_id)

    def mint_quote_key(self, issuer, install_label):
        if issuer.role != "admin":
            raise Forbidden("admin only")
        return self._issue(Principal(None, "quote_client"), KIND_QUOTE_KEY, label=install_label)

    def rotate(self, issuer, credential_id):
        row = self._require(credential_id)
        if not self._policy.can_rotate(issuer, self._scope(row)):
            raise Forbidden("may not rotate")
        token = secrets.token_urlsafe(16)
        self._storage.save(dataclasses.replace(row, token_digest=_sha(token)))
        return IssuedCredential(token, credential_id, row.principal)

    def revoke(self, issuer, credential_id):
        row = self._require(credential_id)
        if not self._policy.can_revoke(issuer, self._scope(row)):
            raise Forbidden("may not revoke")
        self._revoke_tree(row)

    def _revoke_tree(self, row):
        self._storage.save(dataclasses.replace(row, revoked=True))
        for child in self._storage.minted_by(row.principal.agent_id):
            if not child.revoked:
                self._revoke_tree(child)

    # AdminSessions
    def start(self, password):
        if _sha(password) != self._storage.admin_password_hash():
            raise Forbidden("wrong password")
        return self._issue(Principal(None, "admin"), KIND_ADMIN_SESSION,
                           expires_at=self._clock.now() + self._ttl)

    def end(self, session_id):
        self._storage.save(dataclasses.replace(self._require(session_id), revoked=True))
