"""agent_session_keys: persistent keys so agents can resume (carried pattern).

A key is a random token; its SHA-256 digest is stored with no expiry, so it survives restarts.
"""
import secrets
import uuid


class AgentSessionKeys:
    def new_key(self) -> str:
        """A fresh random plaintext token."""
        return secrets.token_urlsafe(32)

    def new_credential_id(self) -> str:
        """A fresh id for a stored credential (not secret)."""
        return f"cred-{uuid.uuid4().hex}"
