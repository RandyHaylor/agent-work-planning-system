"""admin_password_setup: AuthenticationSetup over authentication's PasswordHasher (PBKDF2) and the
credential store's admin-password row (PostgresCredentialStore.set_admin_password_hash)."""
from __future__ import annotations

from planning_system.server.domain.authentication.password_hashing import PasswordHasher

from .ports import AuthenticationSetup


class PasswordHashSetup(AuthenticationSetup):
    def __init__(self, hasher: PasswordHasher | None = None):
        self._hasher = hasher or PasswordHasher()

    def admin_password_set(self, stores):
        raise NotImplementedError("level 7")

    def set_admin_password(self, stores, password):
        raise NotImplementedError("level 7")
