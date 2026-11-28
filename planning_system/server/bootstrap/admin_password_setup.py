"""admin_password_setup: AuthenticationSetup over authentication's PasswordHasher (PBKDF2) and the
credential store's admin-password row (PostgresCredentialStore.set_admin_password_hash)."""
from __future__ import annotations

from planning_system.server.domain.authentication import PasswordHasher

from .ports import AuthenticationSetup


class PasswordHashSetup(AuthenticationSetup):
    def __init__(self, hasher: PasswordHasher | None = None):
        self._hasher = hasher or PasswordHasher()

    def admin_password_set(self, stores):
        return stores.credentials.has_admin_password()

    def set_admin_password(self, stores, password):
        stores.credentials.set_admin_password_hash(self._hasher.hash(password))
