"""token_hashing: SHA-256 digests of tokens (carried). Only digests are stored."""


class TokenHasher:
    def digest(self, token: str) -> str:
        raise NotImplementedError
