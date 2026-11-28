"""Live halt run (build log #68): real HTTPS server (throwaway db), real CLI, a real Haiku task session and a real
Haiku review loop (short paid run), then `planning halt` and the admin server halt.

Proves: every `claude` process this run started is gone after `planning halt` (found by the run's own client home in
each process's environment), the review loop process is gone, the client refuses new starts until `planning resume`,
the halted server refuses writes and review hand-outs (423) while reads work, and admin un-halt works while halted.
Children run outside the repo (a Stop hook re-invokes `claude -p` in the repo cwd). Run:
uv run python -I scripts/live_halt_run.py
"""
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx
import sqlalchemy

REPO = Path(__file__).resolve().parents[1]
DB = "planning_system_halt_smoke"
PORT = 8788
CERT = REPO / "certs" / "server.crt"
CLIENT_HOME = Path(tempfile.gettempdir()) / "planning-live-halt-client"
WORK_DIR = Path(tempfile.gettempdir()) / "planning-live-halt-work"


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


def planning(*args: str) -> list[str]:
    return ["uv", "run", "--project", str(REPO), "planning", *args]


def run(env: dict, *args: str, ok=True):
    proc = subprocess.run(planning(*args), cwd=WORK_DIR, env=env, capture_output=True, text=True)
    shown = " ".join("<token>" if before == "--token" else a if len(a) < 50 else a[:47] + "..."
                     for before, a in zip(("",) + args, args))
    print(f"$ planning {shown}  -> exit {proc.returncode}")
    if ok and proc.returncode != 0:
        print("  stderr:", proc.stderr.strip()[-600:])
        raise SystemExit(1)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except ValueError:
        return proc.returncode, (proc.stdout.strip() or proc.stderr.strip())[-400:]


def our_claude_processes() -> list[tuple[int, str]]:
    """Live (non-zombie) processes whose command is claude and whose environment names this run's client home."""
    marker = f"PLANNING_CLIENT_HOME={CLIENT_HOME}".encode()
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().split(b"\0")
            environ = (entry / "environ").read_bytes().split(b"\0")
            state = (entry / "stat").read_text().rpartition(")")[2].split()[0]
        except OSError:
            continue
        if state != "Z" and marker in environ and any(Path(p.decode(errors="replace")).name == "claude"
                                                      for p in cmdline[:2] if p):
            found.append((int(entry.name), b" ".join(cmdline[:3]).decode(errors="replace")))
    return found


def registry_rows() -> list[dict]:
    try:
        return list(json.loads((CLIENT_HOME / "running-sessions.json").read_text()).values())
    except (OSError, ValueError):
        return []


def wait_for(condition, seconds: float, step: float = 0.2) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(step)
    return False


def main() -> int:
    pw = db_password()
    admin_pw = secrets.token_urlsafe(24)
    shutil.rmtree(CLIENT_HOME, ignore_errors=True)
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    WORK_DIR.mkdir(parents=True)
    base = {**os.environ, "PLANNING_DSN": f"postgresql+psycopg://planner:{pw}@127.0.0.1:5433/{DB}",
            "PLANNING_CLIENT_HOME": str(CLIENT_HOME)}
    if port_open():
        raise SystemExit(f"port {PORT} already in use; stop the other server first")
    drop_db(pw)
    boot = subprocess.run(["uv", "run", "planning-server", "bootstrap"], cwd=REPO,
                          env={**base, "PLANNING_ADMIN_PASSWORD": admin_pw}, capture_output=True, text=True)
    if boot.returncode != 0:
        print("bootstrap failed:", boot.stderr[-800:])
        return 1
    server = subprocess.Popen(["uv", "run", "planning-server", "run"], cwd=REPO, env=base,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    loop = None
    checks: dict[str, bool] = {}
    try:
        wait_for(port_open, 30, 0.5)
        url = f"https://127.0.0.1:{PORT}"
        admin_token = httpx.post(f"{url}/admin/sessions", json={"password": admin_pw},
                                 verify=str(CERT)).json()["token"]
        common = {**base, "PLANNING_URL": url, "PLANNING_CA_CERT": str(CERT)}
        admin = {**common, "PLANNING_TOKEN": admin_token}

        _, project = run(admin, "projects", "create", "--title", "Halt test", "--summary", "Proving halt works.")
        pid = str(project["id"])
        parent = pid
        for title, level in (("Plan", "high-level plan"), ("Design", "design"), ("Modules", "module specs")):
            _, node = run(admin, "nodes", "create", "--parent", parent, "--title", title, "--level", level,
                          "--summary", f"{title} for the halt test.")
            parent = str(node["id"])
        modules = parent
        _, task = run(admin, "nodes", "create", "--parent", modules, "--title", "write a haiku about caches",
                      "--level", "build", "--summary", "Write one short haiku about caches and stop.")
        _, planner_cred = run(admin, "credentials", "mint", "--role", "planner", "--project", pid,
                              "--agent", "planner-1")
        planner = {**common, "PLANNING_TOKEN": planner_cred["token"]}
        worker_agent = str(uuid.uuid4())
        _, assigned = run(planner, "task", "assign", str(task["id"]), "--agent", worker_agent, "--branch", "main")
        worker = {**common, "PLANNING_TOKEN": assigned["worker_token"]}

        _, quote_cred = run(admin, "credentials", "quote-key", "--label", "live-halt")
        user_ref = httpx.post(f"{url}/references/user-exchange", verify=str(CERT),
                              headers={"Authorization": f"Bearer {quote_cred['token']}"},
                              json={"session_id": "s-1", "user_message": "Use 72 hours.",
                                    "pre_text": "How long should cache entries live?"}).json()["reference_id"]
        for text in ("Cache entries live 72 hours", "Cache entries never expire", "Entries last three days",
                     "Entries live 72 hours and are refreshed hourly"):
            run(worker, "content", "add", str(task["id"]), "--tags", "requirement", "--text", f"{text} [{user_ref}:2-2]")
        _, review_task = run(planner, "nodes", "create", "--parent", modules, "--title", "citation review",
                             "--level", "build", "--summary", "Review cited claims.", "--labels", "review")
        _, reviewer_assign = run(planner, "task", "assign", str(review_task["id"]), "--agent", "reviewer-1",
                                 "--branch", "main")
        run(planner, "nodes", "state", str(review_task["id"]), "in_progress")
        reviewer = {**common, "PLANNING_TOKEN": reviewer_assign["worker_token"]}

        # 1. a real Haiku task session (detached, own process group) and a real Haiku review loop
        run(planner, "task", "start", str(task["id"]), "--agent", worker_agent, "--token", assigned["worker_token"],
            "--dir", str(WORK_DIR), "--model", "haiku")
        loop = subprocess.Popen(planning("review", "serve", "--project", pid, "--profile", "haiku",
                                         "--poll-seconds", "1"), cwd=WORK_DIR, env=reviewer,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        saw_reviewer = wait_for(lambda: any(r.get("kind") == "reviewer" for r in registry_rows()), 90)
        print("  registry before halt:", sorted((r.get("kind"), r.get("pid"), r.get("alive")) for r in registry_rows()))
        print("  claude processes before halt:", our_claude_processes())
        checks["a reviewer claude turn was in flight"] = saw_reviewer

        # 2. client halt
        _, report = run(common, "halt")
        print("  halt report:", json.dumps(report))
        kinds = {row["kind"] for row in report["killed"]}
        checks["halt killed task, review loop and reviewer"] = {"task", "review_loop", "reviewer"} <= kinds
        try:
            loop.wait(timeout=10)
            checks["review loop process gone"] = True
        except subprocess.TimeoutExpired:
            checks["review loop process gone"] = False
        gone = wait_for(lambda: not our_claude_processes(), 10)
        print("  claude processes after halt:", our_claude_processes())
        checks["no claude process from this run remains"] = gone
        code, out = run(reviewer, "review", "serve", "--project", pid, "--profile", "haiku", "--once", ok=False)
        checks["halted client starts nothing"] = code != 0 and "halted" in str(out)
        print("  review serve while client halted:", code, str(out)[:160])

        # 3. server halt (admin): writes and review hand-outs refused, reads work, un-halt works while halted
        run(common, "resume")
        _, state = run(admin, "admin", "halt", "--project", pid, "--reason", "live halt test")
        print("  server halt state:", json.dumps(state)[:200])
        code, out = run(worker, "content", "add", str(task["id"]), "--tags", "requirement",
                        "--text", f"Entries live 72 hours [{user_ref}:2-2]", ok=False)
        checks["write refused while server halted"] = code != 0 and "Halted" in str(out)
        print("  write while halted:", code, str(out)[:200])
        code, out = run(reviewer, "review", "serve", "--project", pid, "--profile", "haiku", "--once", ok=False)
        checks["review hand-out refused while server halted"] = code != 0 and "Halted" in str(out)
        print("  take while halted:", code, str(out)[:200])
        code, _ = run(planner, "nodes", "get", str(task["id"]), ok=False)
        checks["reads work while server halted"] = code == 0
        run(admin, "admin", "unhalt", "--project", pid)
        code, _ = run(worker, "content", "add", str(task["id"]), "--tags", "requirement",
                      "--text", f"Entries live 72 hours [{user_ref}:2-2]", ok=False)
        checks["write works again after un-halt"] = code == 0

        # 4. review logging (build log #70): one local_llm review (the existing llama.cpp server), then the log and
        # the reviewer stored with the verdict
        _, taken = run(reviewer, "review", "serve", "--project", pid, "--profile", "local", "--once")
        _, shown = run(planner, "review", "show", taken["review_id"])
        print("  reviewed_with on the server:", shown.get("reviewed_with"))
        checks["server stored the verdict's reviewer"] = (shown.get("reviewed_with") or {}).get("backend") == "local_llm"
        _, logged = run(common, "review", "log", "--last", "5")
        print(f"  review log records: {len(logged)}; "
              f"{[(r.get('review_id'), r.get('backend'), r.get('model_calls'), r.get('error')) for r in logged]}")
        checks["aborted and finished reviews both logged"] = (
            any(str(r.get("error", "")).startswith("ReviewAborted") for r in logged)
            and any(r.get("review_id") == taken["review_id"] and r.get("verdict") for r in logged))
        for name, passed in checks.items():
            print(f"  {'ok  ' if passed else 'FAIL'} {name}")
        good = all(checks.values())
        print("LIVE HALT RUN", "PASSED" if good else "CHECK RESULTS")
        return 0 if good else 1
    finally:
        subprocess.run(planning("halt"), cwd=WORK_DIR, env={**base}, capture_output=True)   # belt and braces
        if loop is not None and loop.poll() is None:
            loop.kill()
        leftover = our_claude_processes()
        if leftover:
            print("  WARNING: claude processes left:", leftover)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        drop_db(pw)


if __name__ == "__main__":
    sys.exit(main())
