"""Clean-state end-to-end on any platform: fresh DB, bootstrap, start server, unit + integration tests, stop.

    uv run python scripts/test_all.py

Env: PLANNER_PORT overrides the port (default 8787). Requires docker compose, uv, and Python 3.10+.
"""
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = os.environ.get("PLANNER_PORT", "8787")
URL = f"https://localhost:{PORT}"


def run(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=ROOT, check=check, text=True, capture_output=capture)


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


def main() -> int:
    run("docker", "compose", "down", "-v", check=False)
    run("docker", "compose", "up", "-d", "--wait")
    run("uv", "sync", "--extra", "test", "--quiet")
    out = run("uv", "run", "python", "-m", "server", "bootstrap", capture=True).stdout
    print(out, end="")
    m = re.search(r"^ROOT_TOKEN=(\S+)$", out, re.M)
    if not m:
        raise SystemExit("bootstrap did not print ROOT_TOKEN")
    token = m.group(1)

    env = dict(os.environ, PLANNER_PORT=PORT)
    log = open(ROOT / "planner-server.log", "w")
    server = subprocess.Popen(["uv", "run", "python", "-m", "server"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_for_server()
        test_env = dict(os.environ, PLANNER_URL=URL, PLANNER_ROOT_TOKEN=token)
        result = subprocess.run(["uv", "run", "pytest", "-q", "server", "tests"], cwd=ROOT, env=test_env)
        return result.returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
