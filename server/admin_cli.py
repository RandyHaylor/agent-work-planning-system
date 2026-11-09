"""CLI side of the admin login: ask the server for a nonce, open the browser login page for the
user, poll until the user has approved, print the session token once.

Talks to the local server over HTTPS without verifying the self-signed cert (localhost only).
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from server import admin as A

TIMEOUT = 120


def base_url() -> str:
    return os.environ.get("PLANNER_URL") or f"https://127.0.0.1:{os.environ.get('PLANNER_PORT', '8787')}"


def _ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _request(method: str, path: str, token: str = None, data: bytes = None):
    req = urllib.request.Request(base_url() + path, method=method, data=data)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, context=_ctx(), timeout=10) as r:
        body = r.read()
        return r.status, (json.loads(body) if body else None)


def login() -> int:
    try:
        _, nonce = _request("POST", "/admin/nonce")
    except (urllib.error.URLError, OSError) as e:
        print(f"server not reachable at {base_url()}: {e}", file=sys.stderr)
        return 1
    url = f"{base_url()}/admin/login?nonce={nonce['nonce']}"
    print(f"Open this page and enter the admin password: {url}", file=sys.stderr)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        try:
            _, got = _request("GET", f"/admin/session/{nonce['nonce']}")
            print(f"ADMIN_TOKEN={got['token']}")
            return 0
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"login failed: {e.code} {e.reason}", file=sys.stderr)
                return 1
        time.sleep(1)
    print("timed out waiting for the user to approve the admin login", file=sys.stderr)
    return 1


def logout() -> int:
    token = os.environ.get("PLANNER_ADMIN_TOKEN")
    if not token or not A.is_session_token(token):
        print("set PLANNER_ADMIN_TOKEN to the adm_... session token", file=sys.stderr)
        return 1
    try:
        _request("POST", "/admin/logout", token=token)
    except urllib.error.HTTPError as e:
        print(f"logout failed: {e.code} {e.reason}", file=sys.stderr)
        return 1
    print("admin session ended")
    return 0
