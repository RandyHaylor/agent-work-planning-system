"""Live paid run (short, Haiku): a real headless Claude Code worker started by `planning task start`.

Throwaway database `planning_system_smoke`, throwaway admin password (never printed), real HTTPS server.
The worker's task content tells it to turn in one line via the planning CLI; the script waits for it.
Run: uv run python -I scripts/live_task_run.py
"""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import sqlalchemy

REPO = Path(__file__).resolve().parents[1]
DB = "planning_system_smoke"
PORT = 8788
CERT = REPO / "certs" / "server.crt"
WAIT_SECONDS = 180


def db_password() -> str:
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith("PLANNER_DB_PASSWORD="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no PLANNER_DB_PASSWORD in .env")


def drop_db(pw: str) -> None:
    engine = sqlalchemy.create_engine(
        f"postgresql+psycopg://planner:{pw}@127.0.0.1:5433/postgres", isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        c.execute(sqlalchemy.text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
    engine.dispose()


def port_open() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def cli(env: dict, *args: str):
    proc = subprocess.run(["uv", "run", "planning", *args], cwd=REPO, env=env, capture_output=True, text=True)
    print(f"$ planning {' '.join(a if len(a) < 60 else a[:57] + '...' for a in args)}  -> exit {proc.returncode}")
    if proc.returncode != 0:
        print("  stderr:", proc.stderr.strip()[-800:])
        raise SystemExit(1)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return proc.stdout.strip()


def main() -> int:
    pw = db_password()
    admin_pw = secrets.token_urlsafe(24)
    base_env = {**os.environ, "PLANNING_DSN": f"postgresql+psycopg://planner:{pw}@127.0.0.1:5433/{DB}",
                "PLANNING_CLIENT_HOME": "/tmp/planning-live-task-client"}
    if port_open():
        raise SystemExit(f"port {PORT} already in use; stop the other server first")
    drop_db(pw)
    boot = subprocess.run(["uv", "run", "planning-server", "bootstrap"], cwd=REPO,
                          env={**base_env, "PLANNING_ADMIN_PASSWORD": admin_pw}, capture_output=True, text=True)
    if boot.returncode != 0:
        print("bootstrap failed:", boot.stderr[-800:])
        return 1
    server = subprocess.Popen(["uv", "run", "planning-server", "run"], cwd=REPO, env=base_env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    agent_id = str(uuid.uuid4())   # also the Claude session id
    try:
        for _ in range(60):
            if port_open():
                break
            time.sleep(0.5)
        url = f"https://127.0.0.1:{PORT}"
        token = httpx.post(f"{url}/admin/sessions", json={"password": admin_pw}, verify=str(CERT)).json()["token"]
        env = {**base_env, "PLANNING_URL": url, "PLANNING_CA_CERT": str(CERT), "PLANNING_TOKEN": token}
        project = cli(env, "projects", "create", "--title", "Live task run",
                      "--summary", "A tiny project to prove a real worker session can use the planning CLI.")
        task = cli(env, "nodes", "create", "--parent", str(project["id"]), "--title", "Turn-in check",
                   "--level", "definition of done", "--summary", "Checks that a worker can turn in a response.")
        node_id = str(task["id"])
        cli(env, "content", "add", node_id, "--tags", "instructions", "--text",
            f"Your task: run exactly `uv run planning content add {node_id} --tags response --text "
            "\"worker online\"` (PLANNING_URL, PLANNING_TOKEN and PLANNING_CA_CERT are already set in your "
            "environment). Then reply DONE. Do nothing else.")
        assigned = cli(env, "task", "assign", node_id, "--agent", agent_id, "--branch", "none")
        cli(env, "task", "start", node_id, "--agent", agent_id, "--token", assigned["worker_token"],
            "--dir", str(REPO), "--model", "haiku", "--allow-tools", "Bash(uv run planning:*)")
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            content = cli(env, "nodes", "get", node_id)
            texts = json.loads(subprocess.run(
                ["uv", "run", "planning", "nodes", "context", node_id], cwd=REPO, env=env,
                capture_output=True, text=True).stdout)["text"]
            # The instructions contain the phrase once; the worker's response adds a second occurrence.
            if texts.count("worker online") >= 2:
                print("worker response found in the node's content")
                print("LIVE TASK RUN PASSED")
                return 0
            time.sleep(10)
        log = Path(base_env["PLANNING_CLIENT_HOME"]) / "sessions" / f"{agent_id}.ndjson"
        print("no response within", WAIT_SECONDS, "s; session log tail:")
        if log.exists():
            print(log.read_text()[-3000:])
        return 1
    finally:
        subprocess.run(["uv", "run", "planning", "task", "stop", agent_id], cwd=REPO,
                       env={**base_env}, capture_output=True)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        drop_db(pw)


if __name__ == "__main__":
    sys.exit(main())
