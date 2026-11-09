"""Clean-state end-to-end on any platform, isolated from the live planning database.

    uv run python scripts/test_all.py

Uses its own compose project (`planner-test`), its own DB host port, its own random DB
password and a temp backup dir, so the live `docker compose` project, its volume, its
.env and its backups directory are never touched. Starts a fresh Postgres, bootstraps,
starts the server, runs unit + integration tests, then stops the server and tears the
test compose project down with its volume.

Env:
  PLANNER_PORT      HTTPS port for the server under test (default 8787)
  PLANNER_DB_PORT   host port for the test Postgres (default 5434; live default is 5433)
Requires docker compose, uv, Python 3.10+.
"""
import os
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = os.environ.get("PLANNER_PORT", "8787")
DB_PORT = os.environ.get("PLANNER_DB_PORT", "5434")
URL = f"https://localhost:{PORT}"
PASSWORD = secrets.token_urlsafe(16)
DSN = f"postgresql://planner:{PASSWORD}@127.0.0.1:{DB_PORT}/planner"
COMPOSE = ["docker", "compose", "-p", "planner-test"]


def run(args: list[str], env: dict, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, env=env, check=check, text=True, capture_output=capture)


def wait_for_server(timeout: float = 20.0) -> None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{URL}/me", context=ctx, timeout=1)
            return
        except urllib.error.HTTPError:
            return  # 401 means the server is answering
        except Exception:
            time.sleep(0.25)
    raise SystemExit(f"server did not answer on {URL}")


def port_free(port: int) -> bool:
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    if not port_free(int(PORT)):
        raise SystemExit(f"port {PORT} is already in use; set PLANNER_PORT to a free port so the tests hit the server under test")
    backup_dir = tempfile.mkdtemp(prefix="planner-test-backups-")
    env = dict(os.environ, PLANNER_DB_PORT=DB_PORT, PLANNER_DB_PASSWORD=PASSWORD, PLANNER_DSN=DSN,
               PLANNER_PORT=PORT, PLANNER_URL=URL, PLANNER_BACKUP_DIR=backup_dir)
    run(COMPOSE + ["down", "-v"], env, check=False)
    run(COMPOSE + ["up", "-d", "--wait"], env)
    server = None
    log = open(ROOT / "planner-server.log", "w")
    try:
        run(["uv", "sync", "--extra", "test", "--quiet"], env)
        out = run(["uv", "run", "python", "-m", "server", "bootstrap"], env, capture=True).stdout
        print(out, end="")
        m = re.search(r"^ADMIN_TOKEN=(\S+)$", out, re.M)
        if not m:
            raise SystemExit("bootstrap did not print ADMIN_TOKEN")
        env["PLANNER_ADMIN_TOKEN"] = m.group(1)
        server = subprocess.Popen(["uv", "run", "python", "-m", "server"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        wait_for_server()
        return subprocess.run(["uv", "run", "pytest", "-q", "server", "tests"], cwd=ROOT, env=env).returncode
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        log.close()
        run(COMPOSE + ["down", "-v"], env, check=False)


if __name__ == "__main__":
    sys.exit(main())
