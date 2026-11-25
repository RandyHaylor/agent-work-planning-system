"""Test support: in-memory credential storage holding a real PBKDF2 admin hash (for the real classes)."""
from planning_system.server.domain.authentication.fakes import InMemoryCredentialStorage
from planning_system.server.domain.authentication.password_hashing import PasswordHasher


class PbkdfCredentialStorage(InMemoryCredentialStorage):
    def __init__(self, admin_password: str):
        super().__init__(admin_password)
        self._admin_hash = PasswordHasher().hash(admin_password)
