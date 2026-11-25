"""Live smoke test against a THROWAWAY database (planning_system_smoke). Never touches planning_system.

Admin password is generated here and never printed (log #42/#44). Prints each CLI call and a short result.
"""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import sqlalchemy

REPO = Path("/home/aikenyon/ai_skills_agents_resources/agent-work-planning-system")
DB = "planning_system_smoke"
PORT = 8788
CERT = REPO / "certs" / "server.crt"
FIXTURE = REPO / "tests/planning_system/end_to_end/fixtures/caching_guide.html"


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


def cli(env: dict, *args: str) -> dict:
    proc = subprocess.run(["uv", "run", "planning", *args], cwd=REPO, env=env, capture_output=True, text=True)
    out = proc.stdout.strip()
    print(f"$ planning {' '.join(args)}  -> exit {proc.returncode}")
    if proc.returncode != 0:
        print("  stderr:", proc.stderr.strip()[-800:])
        raise SystemExit(1)
    try:
        data = json.loads(out)
    except ValueError:
        data = {"text": out}
    print("  ", (json.dumps(data) if not isinstance(data, str) else data)[:300])
    return data


def main() -> int:
    pw = db_password()
    admin_pw = secrets.token_urlsafe(24)
    base_env = dict(os.environ)
    base_env["PLANNING_DSN"] = f"postgresql+psycopg://planner:{pw}@127.0.0.1:5433/{DB}"
    base_env["PLANNING_CLIENT_HOME"] = str(Path(os.environ.get("SMOKE_CLIENT_HOME", "/tmp/planning-smoke-client")))
    if port_open():
        raise SystemExit(f"port {PORT} already in use; stop the other server first")
    drop_db(pw)
    boot = subprocess.run(["uv", "run", "planning-server", "bootstrap"], cwd=REPO,
                          env={**base_env, "PLANNING_ADMIN_PASSWORD": admin_pw}, capture_output=True, text=True)
    print("bootstrap exit", boot.returncode, boot.stdout.strip()[-300:], boot.stderr.strip()[-500:])
    if boot.returncode != 0:
        return 1
    server = subprocess.Popen(["uv", "run", "planning-server", "run"], cwd=REPO, env=base_env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(60):
            if port_open():
                break
            if server.poll() is not None:
                print("server exited:", server.stdout.read()[-2000:])
                return 1
            time.sleep(0.5)
        else:
            print("server did not open its port")
            return 1
        url = f"https://127.0.0.1:{PORT}"
        admin = httpx.post(f"{url}/admin/sessions", json={"password": admin_pw}, verify=str(CERT)).json()
        token = admin["token"]
        env = {**base_env, "PLANNING_URL": url, "PLANNING_CA_CERT": str(CERT), "PLANNING_TOKEN": token}
        cli(env, "me")
        project = cli(env, "projects", "create", "--title", "Smoke project", "--summary", "A smoke-test project.")
        pid = str(project["id"])
        dod = cli(env, "nodes", "create", "--parent", pid, "--title", "Definition of done",
                  "--level", "definition of done", "--summary", "What done means.")
        task = cli(env, "nodes", "create", "--parent", str(dod["id"]), "--title", "Caching module",
                   "--level", "build", "--summary", "Builds the caching module.")
        assigned = cli(env, "task", "assign", str(task["id"]), "--agent", "smoke-worker", "--branch", "feat/smoke")
        worker_env = {**env, "PLANNING_TOKEN": assigned["worker_token"]}
        cli(worker_env, "me")
        cli(worker_env, "supplementary", "create", "--kind", "tech_spike", "--title", "Cache library spike",
            "--summary", "Which cache library fits.")
        loaded = cli(env, "load", str(FIXTURE))
        item = loaded[0] if isinstance(loaded, list) else loaded
        cache_id = item.get("cache_id") or item.get("id")
        cli(env, "toc", cache_id)
        cli(env, "search", "cache", "--ids", cache_id)
        cited = cli(env, "cite", cache_id, "1", "3")
        ref_id = cited.get("reference_id")
        cli(env, "references", "lines", ref_id, "--start", "1", "--end", "3")
        cli(env, "nodes", "context", str(task["id"]))
        cli(env, "guidance", "worker")
        quote = cli(env, "credentials", "quote-key", "--label", "smoke-install")
        # The Claude Code UserPromptSubmit hook, invoked exactly as Claude Code would (JSON on stdin).
        payload = {"session_id": "smoke-session", "prompt": "yes, use a 5 minute TTL",
                   "transcript_path": "/nonexistent/transcript.jsonl", "hook_event_name": "UserPromptSubmit",
                   "cwd": str(REPO)}
        hook = subprocess.run(["uv", "run", "python", "-m",
                               "planning_system.local_client.harness_adapters.claude_code.user_prompt_submit_hook"],
                              cwd=REPO, env=env, input=json.dumps(payload), capture_output=True, text=True)
        print("hook exit", hook.returncode, hook.stderr.strip()[-300:])
        exchanges = cli(env, "client", "exchanges", "--last", "1")
        first = exchanges[0] if isinstance(exchanges, list) else exchanges
        local_id = first.get("local_id") or first.get("id")
        synced = cli(env, "cite-exchange", str(local_id))
        ref = synced.get("reference_id") if isinstance(synced, dict) else synced
        got = cli(env, "references", "get", str(ref))
        assert "yes, use a 5 minute TTL" in json.dumps(got), "synced exchange text missing"
        print("SMOKE TEST PASSED")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        drop_db(pw)


if __name__ == "__main__":
    sys.exit(main())
