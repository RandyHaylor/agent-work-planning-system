"""Unit tests for the admin password and session store. Pure, no IO."""
from server import admin as A


def test_password_hash_roundtrip():
    salt, h = A.hash_password("correct horse battery")
    assert A.verify_password("correct horse battery", salt, h)
    assert not A.verify_password("wrong", salt, h)
    assert A.check_password_policy("short") and A.check_password_policy("long enough") is None


def test_nonce_login_pickup_once():
    s = A.SessionStore()
    n = s.new_nonce(now=1000.0)
    assert s.nonce_valid(n, now=1010.0)
    assert not s.nonce_valid("bogus", now=1010.0)
    assert not s.nonce_valid(n, now=1000.0 + s.nonce_ttl + 1)
    tok = s.login(n, now=1010.0)
    assert tok.startswith("adm_") and not s.nonce_valid(n, now=1011.0)
    assert s.pickup(n, now=1011.0) == tok
    assert s.pickup(n, now=1012.0) is None  # exactly once
    assert s.touch(tok, now=1020.0)


def test_pickup_expires_and_kills_session():
    s = A.SessionStore()
    n = s.new_nonce(now=0.0)
    tok = s.login(n, now=0.0)
    assert s.pickup(n, now=s.nonce_ttl + 1) is None
    assert not s.touch(tok, now=s.nonce_ttl + 2)


def test_idle_expiry_logout_and_clear():
    s = A.SessionStore(idle_seconds=100)
    tok = s.login(s.new_nonce(now=0.0), now=0.0)
    assert s.touch(tok, now=90.0) and s.touch(tok, now=180.0)  # last_used slides
    assert not s.touch(tok, now=300.0)
    tok2 = s.login(s.new_nonce(now=0.0), now=0.0)
    assert s.logout(tok2) and not s.logout(tok2) and not s.touch(tok2, now=1.0)
    tok3 = s.login(s.new_nonce(now=0.0), now=0.0)
    s.clear()
    assert not s.touch(tok3, now=1.0)


def test_rate_limit_window():
    s = A.SessionStore(fail_limit=3, fail_window=10)
    for t in (0.0, 1.0, 2.0):
        assert not s.rate_limited(now=t)
        s.record_failure(now=t)
    assert s.rate_limited(now=3.0)
    assert not s.rate_limited(now=13.0)
