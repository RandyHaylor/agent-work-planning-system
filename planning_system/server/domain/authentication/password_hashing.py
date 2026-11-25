"""password_hashing: salted PBKDF2-HMAC-SHA256, 600,000 iterations (carried from the old admin.py).

Stored format: "pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>", so the salt and iteration
count travel with the hash in one column.
"""
import hashlib
import hmac
import secrets

ITERATIONS = 600_000
SCHEME = "pbkdf2_sha256"


def _derive(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


class PasswordHasher:
    def __init__(self, iterations: int = ITERATIONS):
        self._iterations = iterations

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        return f"{SCHEME}${self._iterations}${salt.hex()}${_derive(password, salt, self._iterations)}"

    def verify(self, password: str, stored_hash: str) -> bool:
        try:
            scheme, iterations, salt_hex, hash_hex = stored_hash.split("$")
            salt, rounds = bytes.fromhex(salt_hex), int(iterations)
        except ValueError:
            return False
        if scheme != SCHEME:
            return False
        return hmac.compare_digest(_derive(password, salt, rounds), hash_hex)
