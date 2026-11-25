"""token_hashing: SHA-256 digests of tokens (carried). Only digests are stored."""
import hashlib


class TokenHasher:
    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
