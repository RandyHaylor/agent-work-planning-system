"""admin_session: temporary admin sessions started by the password popup (carried pattern)."""
from datetime import timedelta

from .agent_session_keys import AgentSessionKeys
from .interface import AdminSessions
from .password_hashing import PasswordHasher
from .token_hashing import TokenHasher


class AdminSessionService(AdminSessions):
    def __init__(self, storage, clock, ttl: timedelta = timedelta(hours=8),
                 passwords: PasswordHasher | None = None, keys: AgentSessionKeys | None = None,
                 hasher: TokenHasher | None = None):
        self._storage = storage
        self._clock = clock
        self._ttl = ttl
        self._passwords = passwords or PasswordHasher()
        self._keys = keys or AgentSessionKeys()
        self._hasher = hasher or TokenHasher()

    def start(self, password):
        raise NotImplementedError

    def end(self, session_id):
        raise NotImplementedError
