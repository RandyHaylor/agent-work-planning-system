"""password_hashing: PBKDF2, 600,000 iterations (carried)."""

ITERATIONS = 600_000


class PasswordHasher:
    def hash(self, password: str) -> str:
        raise NotImplementedError

    def verify(self, password: str, stored_hash: str) -> bool:
        raise NotImplementedError
