"""admin_session: temporary admin sessions started by the password popup (carried pattern)."""
from dataclasses import replace
from datetime import timedelta

from planning_system.contract import Forbidden, NotFound, Principal
from planning_system.server.domain.access.types import ADMIN

from .agent_session_keys import AgentSessionKeys
from .interface import AdminSessions
from .issuing import TokenIssuing
from .password_hashing import PasswordHasher
from .token_hashing import TokenHasher
from .types import KIND_ADMIN_SESSION


class AdminSessionService(AdminSessions):
    def __init__(self, storage, clock, ttl: timedelta = timedelta(hours=8),
                 passwords: PasswordHasher | None = None, keys: AgentSessionKeys | None = None,
                 hasher: TokenHasher | None = None):
        self._storage = storage
        self._clock = clock
        self._ttl = ttl
        self._passwords = passwords or PasswordHasher()
        self._issuing = TokenIssuing(storage, keys or AgentSessionKeys(), hasher or TokenHasher())

    def start(self, password):
        if not self._passwords.verify(password, self._storage.admin_password_hash()):
            raise Forbidden("wrong password")
        return self._issuing.issue(Principal(None, ADMIN), KIND_ADMIN_SESSION,
                                   expires_at=self._clock.now() + self._ttl)

    def end(self, session_id):
        stored = self._storage.get(session_id)
        if stored is None or stored.kind != KIND_ADMIN_SESSION:
            raise NotFound(f"admin session {session_id}")
        self._storage.save(replace(stored, revoked=True))
