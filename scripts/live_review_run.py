"""Live review-mode run: real HTTPS server (throwaway db), real CLI, real reviewer backends.

- local_llm: the existing llama.cpp gemma4 server (127.0.0.1:8898; one shared slot, short calls).
- claude_code: headless `claude -p --model haiku` (short paid run).
The user's words arrive through the quote key; a worker writes one claim the quote supports and one it
contradicts; `planning review serve --once` reviews them, then the whole-node guess screen (build log #60 (5))
screens the node; the planner can't mark the task done while a review failed. Run: uv run python -I scripts/live_review_run.py [--skip-claude]
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

REPO = Path(__file__).resolve().parents[1]
DB = "planning_system_smoke"
PORT = 8788
CERT = REPO / "certs" / "server.crt"


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


def run(env: dict, *args: str, ok=True):
    proc = subprocess.run(["uv", "run", "planning", *args], cwd=REPO, env=env, capture_output=True, text=True)
    shown = " ".join(a if len(a) < 50 else a[:47] + "..." for a in args)
    print(f"$ planning {shown}  -> exit {proc.returncode}")
    if ok and proc.returncode != 0:
        print("  stderr:", proc.stderr.strip()[-600:])
        raise SystemExit(1)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except ValueError:
        return proc.returncode, proc.stdout.strip() or proc.stderr.strip()[-300:]


def main() -> int:
    skip_claude = "--skip-claude" in sys.argv
    pw = db_password()
    admin_pw = secrets.token_urlsafe(24)
    base = {**os.environ, "PLANNING_DSN": f"postgresql+psycopg://planner:{pw}@127.0.0.1:5433/{DB}",
            "PLANNING_CLIENT_HOME": "/tmp/planning-live-review-client"}
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
    try:
        for _ in range(60):
            if port_open():
                break
            time.sleep(0.5)
        url = f"https://127.0.0.1:{PORT}"
        admin_token = httpx.post(f"{url}/admin/sessions", json={"password": admin_pw},
                                 verify=str(CERT)).json()["token"]
        common = {**base, "PLANNING_URL": url, "PLANNING_CA_CERT": str(CERT)}
        admin = {**common, "PLANNING_TOKEN": admin_token}

        _, project = run(admin, "projects", "create", "--title", "Cache service",
                         "--summary", "We are building a caching service.")
        pid = str(project["id"])
        parent = pid
        for title, level in (("Plan", "high-level plan"), ("Design", "design"), ("Modules", "module specs")):
            _, node = run(admin, "nodes", "create", "--parent", parent, "--title", title, "--level", level,
                          "--summary", f"{title} for the cache.")
            parent = str(node["id"])
        modules = parent
        _, task = run(admin, "nodes", "create", "--parent", modules, "--title", "cache lifetime",
                      "--level", "build", "--summary", "How long entries live.")
        _, planner_cred = run(admin, "credentials", "mint", "--role", "planner", "--project", pid,
                              "--agent", "planner-1")
        planner = {**common, "PLANNING_TOKEN": planner_cred["token"]}
        _, assigned = run(planner, "task", "assign", str(task["id"]), "--agent", "worker-1", "--branch", "feat/ttl")
        worker = {**common, "PLANNING_TOKEN": assigned["worker_token"]}

        # the user's words, via the quote key (what the Claude Code hook + cite-exchange do)
        _, quote_cred = run(admin, "credentials", "quote-key", "--label", "live-review")
        stored = httpx.post(f"{url}/references/user-exchange", verify=str(CERT),
                            headers={"Authorization": f"Bearer {quote_cred['token']}"},
                            json={"session_id": "s-1", "user_message": "Use 72 hours.",
                                  "pre_text": "How long should cache entries live?"}).json()
        user_ref = stored["reference_id"]
        print("user quote stored as", user_ref)

        code, _ = run(worker, "content", "add", str(task["id"]), "--tags", "requirement",
                      "--text", "Cache entries live 72 hours.", ok=False)
        print("  uncited requirement rejected:", code != 0)
        run(worker, "content", "add", str(task["id"]), "--tags", "requirement",
            "--text", f"Cache entries live 72 hours [{user_ref}:2-2]")
        run(worker, "content", "add", str(task["id"]), "--tags", "requirement",
            "--text", f"Cache entries never expire [{user_ref}:2-2]")

        _, review_task = run(planner, "nodes", "create", "--parent", modules, "--title", "citation review",
                             "--level", "build", "--summary", "Review cited claims.", "--labels", "review")
        _, reviewer_assign = run(planner, "task", "assign", str(review_task["id"]), "--agent", "reviewer-1",
                                 "--branch", "main")
        run(planner, "nodes", "state", str(review_task["id"]), "in_progress")
        reviewer = {**common, "PLANNING_TOKEN": reviewer_assign["worker_token"]}

        backends = [("local_llm", None), ("local_llm", None)]          # the two claims, oldest first
        if not skip_claude:
            run(worker, "content", "add", str(task["id"]), "--tags", "requirement",
                "--text", f"Entries expire after three days [{user_ref}:2-2]")
            backends.append(("claude_code", "haiku"))
        backends.append(("local_llm", None))                             # then the whole-node guess screen
        for backend, model in backends:
            args = ["review", "serve", "--project", pid, "--backend", backend, "--once"]
            if model:
                args += ["--model", model]
            started = time.monotonic()
            run(reviewer, *args)
            print(f"  {backend} review took {time.monotonic() - started:.1f}s")

        _, listed = run(planner, "review", "list", "--project", pid)
        for r in listed:
            print(f"  review {r.get('id')}: {r.get('status')}  reason={str(r.get('reason'))[:120]!r}")
        statuses = [r.get("status") for r in listed if r.get("target_kind") == "content"]
        node_reviews = [r for r in listed if r.get("target_kind") == "node" and r.get("status") != "superseded"]
        code, out = run(planner, "nodes", "state", str(task["id"]), "done", ok=False)
        print("  task 'done' while a review failed ->", "rejected" if code != 0 else "ALLOWED", str(out)[:200])
        node_screened = len(node_reviews) == 1 and node_reviews[0].get("status") in ("passed", "failed")
        print("  whole-node guess screen decided:", node_screened)
        good = (statuses.count("passed") >= 1 + (0 if skip_claude else 1) and statuses.count("failed") == 1
                and node_screened)

        # supersede (05-spec-reference-supersede.md): a new user quote that changes the cited one -> the all-quotes
        # check (one call) -> a candidate -> trial reviews of the items citing the old quote -> requirement request
        newer = httpx.post(f"{url}/references/user-exchange", verify=str(CERT),
                           headers={"Authorization": f"Bearer {quote_cred['token']}"},
                           json={"session_id": "s-1", "user_message": "Make it 24 hours.",
                                 "pre_text": "Is 72 hours still right for cache entries?"}).json()["reference_id"]
        _, expiry = run(planner, "nodes", "create", "--parent", modules, "--title", "entry expiry", "--level",
                        "build", "--summary", "When entries expire.")
        run(planner, "content", "add", str(expiry["id"]), "--tags", "requirement",
            "--text", f"Cache entries expire after 24 hours [{newer}:2-2]")
        for _ in range(8):
            _, pending = run(planner, "review", "list", "--project", pid, "--status", "pending")
            if not pending:
                break
            started = time.monotonic()
            run(reviewer, "review", "serve", "--project", pid, "--backend", "local_llm", "--once")
            print(f"  local_llm {pending[0].get('target_kind')} review took {time.monotonic() - started:.1f}s")
        _, listed = run(planner, "review", "list", "--project", pid)
        for r in listed:
            if r.get("target_kind") in ("quote_check", "trial"):
                print(f"  {r.get('target_kind')} {r.get('status')}: {str(r.get('reason'))[:140]!r}")
        _, candidates = run(planner, "references", "candidates", "--project", pid)
        for c in candidates:
            print(f"  candidate {c['id']}: {c['old_reference_id']} -> {c['new_reference_id']} {c['kind']} "
                  f"{c['found_by']} {c['status']} request node {c.get('request_node_id')}")
        supersede_ok = any(c["found_by"] == "quote_check" and c["old_reference_id"] == user_ref
                           and c["status"] == "trial_reviewed" for c in candidates)
        print("  supersede candidate found and trial reviewed:", supersede_ok)
        good = good and supersede_ok
        print("LIVE REVIEW RUN", "PASSED" if good and code != 0 else "CHECK RESULTS")
        return 0 if good and code != 0 else 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        drop_db(pw)


if __name__ == "__main__":
    sys.exit(main())
