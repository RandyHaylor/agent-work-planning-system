"""Admin password and admin sessions.

The admin is not a token in the database. It is a user-approved session:
- bootstrap stores a salted PBKDF2-HMAC-SHA256 hash of a password only the user knows;
- an agent that wants to act as admin runs ``uv run ai-project-planning-server admin-login``, which opens a
  browser page where the user types the password directly into the server;
- the server hands back a session token (``adm_...``) kept only in this process's memory,
  so it never survives a server restart and ends at ``POST /admin/logout`` or after idling.

Everything here is pure Python on plain values, so it can be unit tested without a server.
"""
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LEN = 8
NONCE_TTL = 120.0            # seconds a login nonce, and a picked-up-once session, stays valid
FAIL_LIMIT = 5               # failed logins per window before 429
FAIL_WINDOW = float(os.environ.get("PLANNER_ADMIN_FAIL_WINDOW", "60"))
IDLE_SECONDS = float(os.environ.get("PLANNER_ADMIN_IDLE_HOURS", "8")) * 3600
SESSION_PREFIX = "adm_"


# ---------- password ----------

def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """Return (salt_hex, hash_hex)."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    _, got = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(got, hash_hex)


def check_password_policy(password: str) -> Optional[str]:
    if len(password) < MIN_PASSWORD_LEN:
        return f"password must be at least {MIN_PASSWORD_LEN} characters"
    return None


# ---------- sessions, nonces, rate limit (in-memory, per server process) ----------

@dataclass
class Session:
    created: float
    last_used: float


@dataclass
class SessionStore:
    """Admin sessions live only here. A restart clears them."""
    sessions: dict = field(default_factory=dict)      # token -> Session
    nonces: dict = field(default_factory=dict)        # nonce -> registered_at (awaiting login)
    pending: dict = field(default_factory=dict)       # nonce -> (token, created_at) (login done, not picked up)
    failures: list = field(default_factory=list)      # timestamps of failed logins
    idle_seconds: float = IDLE_SECONDS
    nonce_ttl: float = NONCE_TTL
    fail_limit: int = FAIL_LIMIT
    fail_window: float = FAIL_WINDOW

    # nonces
    def new_nonce(self, now: Optional[float] = None) -> str:
        now = time.time() if now is None else now
        self._sweep(now)
        n = secrets.token_urlsafe(32)
        self.nonces[n] = now
        return n

    def nonce_valid(self, nonce: str, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        t = self.nonces.get(nonce)
        return t is not None and now - t <= self.nonce_ttl

    # login
    def rate_limited(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        self.failures = [t for t in self.failures if now - t <= self.fail_window]
        return len(self.failures) >= self.fail_limit

    def record_failure(self, now: Optional[float] = None) -> None:
        self.failures.append(time.time() if now is None else now)

    def login(self, nonce: str, now: Optional[float] = None) -> str:
        """Password already verified by the caller. Consume the nonce, create a session, park it for pickup."""
        now = time.time() if now is None else now
        self.nonces.pop(nonce, None)
        token = SESSION_PREFIX + secrets.token_urlsafe(32)
        self.sessions[token] = Session(created=now, last_used=now)
        self.pending[nonce] = (token, now)
        return token

    def pickup(self, nonce: str, now: Optional[float] = None) -> Optional[str]:
        """Return the session token for a completed login exactly once."""
        now = time.time() if now is None else now
        item = self.pending.pop(nonce, None)
        if item is None:
            return None
        token, created = item
        if now - created > self.nonce_ttl:
            self.sessions.pop(token, None)
            return None
        return token

    # auth
    def touch(self, token: str, now: Optional[float] = None) -> bool:
        """True if the token is a live session; updates last_used."""
        now = time.time() if now is None else now
        s = self.sessions.get(token)
        if s is None:
            return False
        if now - s.last_used > self.idle_seconds:
            del self.sessions[token]
            return False
        s.last_used = now
        return True

    def logout(self, token: str) -> bool:
        return self.sessions.pop(token, None) is not None

    def clear(self) -> None:
        self.sessions.clear()
        self.pending.clear()
        self.nonces.clear()

    def _sweep(self, now: float) -> None:
        self.nonces = {n: t for n, t in self.nonces.items() if now - t <= self.nonce_ttl}
        for n, (tok, t) in list(self.pending.items()):
            if now - t > self.nonce_ttl:
                del self.pending[n]
                self.sessions.pop(tok, None)


def is_session_token(bearer: str) -> bool:
    return bearer.startswith(SESSION_PREFIX)


# ---------- login page ----------

LOGIN_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Planning server: admin login</title>
<style>body{font-family:system-ui,sans-serif;max-width:28rem;margin:4rem auto;padding:0 1rem}
input,button{font-size:1rem;padding:.5rem;width:100%%;box-sizing:border-box;margin-top:.5rem}
.msg{color:#a00}</style></head>
<body><h1>Admin login</h1>
<p>An agent asked to act as admin on this planning server. Enter the admin password to approve it.
The agent never sees the password; it receives a session that ends when the server restarts.</p>
%(msg)s
<form method="post" action="/admin/login">
<input type="hidden" name="nonce" value="%(nonce)s">
<label>Password <input type="password" name="password" autofocus autocomplete="current-password"></label>
<button type="submit">Approve</button>
</form></body></html>
"""

DONE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Approved</title></head>
<body style="font-family:system-ui,sans-serif;max-width:28rem;margin:4rem auto;padding:0 1rem">
<h1>Approved</h1><p>The agent now has an admin session. You can close this window.</p></body></html>
"""


def login_page(nonce: str, msg: str = "") -> str:
    m = f'<p class="msg">{msg}</p>' if msg else ""
    return LOGIN_PAGE % {"nonce": nonce, "msg": m}
