"""Contract tests for authentication (spec: planning/05-spec-authentication.md); mocked credential storage."""
from datetime import timedelta

import pytest

from planning_system.contract import DomainError, Forbidden, Principal
from planning_system.server.domain.access.fakes import TablePermissionPolicy
from planning_system.server.domain.authentication.admin_session import AdminSessionService
from planning_system.server.domain.authentication.credential_authenticator import \
    CredentialAuthenticatorService
from planning_system.server.domain.authentication.credential_issuer import CredentialIssuerService
from planning_system.server.domain.authentication.fakes import (FakeAuthentication, FakeClock,
                                                                InMemoryCredentialStorage)

from authentication_test_support import PbkdfCredentialStorage

ADMIN_PASSWORD = "only-the-human-knows"
TTL = timedelta(hours=1)


class Auth:
    """The three interfaces over one storage; build() makes fresh instances (a 'restart')."""

    def __init__(self, kind):
        self.kind = kind
        storage_class = InMemoryCredentialStorage if kind == "fake" else PbkdfCredentialStorage
        self.storage = storage_class(ADMIN_PASSWORD)
        self.clock = FakeClock()
        self.build()

    def build(self):
        policy = TablePermissionPolicy()
        if self.kind == "fake":
            fake = FakeAuthentication(self.storage, policy, self.clock, TTL)
            self.authenticator = self.issuer = self.sessions = fake
        else:
            self.authenticator = CredentialAuthenticatorService(self.storage, self.clock)
            self.issuer = CredentialIssuerService(self.storage, policy)
            self.sessions = AdminSessionService(self.storage, self.clock, TTL)


@pytest.fixture(params=["fake", "real"])
def auth(request):
    return Auth(request.param)


ADMIN = Principal(None, "admin")


def test_1_minted_token_authenticates_to_the_right_principal(auth):
    issued = auth.issuer.mint(ADMIN, "planner", 1, 1, "agent-p")
    principal = auth.authenticator.authenticate(issued.token)
    assert principal == Principal("agent-p", "planner", 1, 1)
    with pytest.raises(Forbidden):
        auth.authenticator.authenticate("not-a-token")


def test_2_only_the_digest_is_stored(auth):
    issued = auth.issuer.mint(ADMIN, "planner", 1, 1, "agent-p")
    stored = auth.storage.get(issued.credential_id)
    assert stored is not None
    assert issued.token not in repr(stored)
    assert all(issued.token not in repr(row) for row in auth.storage.rows.values())


def test_3_revoking_a_planner_revokes_workers_it_minted(auth):
    planner = auth.issuer.mint(ADMIN, "planner", 1, 1, "agent-p")
    worker = auth.issuer.mint(planner.principal, "worker", 1, 5, "agent-w")
    auth.issuer.revoke(ADMIN, planner.credential_id)
    for token in (planner.token, worker.token):
        with pytest.raises(Forbidden):
            auth.authenticator.authenticate(token)


def test_4_rotated_old_token_fails_new_works(auth):
    issued = auth.issuer.mint(ADMIN, "planner", 1, 1, "agent-p")
    rotated = auth.issuer.rotate(ADMIN, issued.credential_id)
    assert rotated.token != issued.token
    with pytest.raises(Forbidden):
        auth.authenticator.authenticate(issued.token)
    assert auth.authenticator.authenticate(rotated.token).agent_id == "agent-p"


def test_5_agent_session_key_survives_restart(auth):
    issued = auth.issuer.mint(ADMIN, "worker", 1, 5, "agent-w")
    auth.clock.advance(timedelta(days=30))
    auth.build()
    assert auth.authenticator.authenticate(issued.token).agent_id == "agent-w"


def test_6_admin_session_needs_password_and_ends_or_expires(auth):
    with pytest.raises(Forbidden):
        auth.sessions.start("wrong")
    session = auth.sessions.start(ADMIN_PASSWORD)
    assert auth.authenticator.authenticate(session.token).role == "admin"
    auth.sessions.end(session.credential_id)
    with pytest.raises(Forbidden):
        auth.authenticator.authenticate(session.token)

    expiring = auth.sessions.start(ADMIN_PASSWORD)
    auth.clock.advance(TTL + timedelta(seconds=1))
    with pytest.raises(Forbidden):
        auth.authenticator.authenticate(expiring.token)


def test_7_quote_key_is_quote_client_and_nothing_else(auth):
    key = auth.issuer.mint_quote_key(ADMIN, "laptop-1")
    principal = auth.authenticator.authenticate(key.token)
    assert principal.role == "quote_client"
    assert principal.agent_id is None and principal.project_id is None
    with pytest.raises(DomainError):
        auth.issuer.mint(principal, "worker", 1, 5, "agent-w")
    with pytest.raises(DomainError):
        auth.issuer.mint_quote_key(principal, "another")
