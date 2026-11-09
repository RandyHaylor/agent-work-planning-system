"""Startup order, run by the planner once per machine (steps 1-3 once; step 4 each session):

    uv run ai-project-planning-server init-env            # 1. random DB password -> .env (gitignored); refuses to overwrite
    docker compose up -d --wait                           # 2. Postgres, bound to 127.0.0.1, password from .env
    uv run ai-project-planning-server bootstrap           # 3. schema + root tree; asks the user for the admin password
    uv run ai-project-planning-server                     # 4. HTTPS on 127.0.0.1:8787 (PLANNER_HOST / PLANNER_PORT)

Becoming admin (an agent runs this; the user types the password into the browser window it opens):

    uv run ai-project-planning-server admin-login         # prints ADMIN_TOKEN=adm_... once; dies with the server
    uv run ai-project-planning-server admin-logout        # ends the session in PLANNER_ADMIN_TOKEN
    uv run ai-project-planning-server set-admin-password  # change the password on an existing database

`python -m ai_project_planning_server <cmd>` is equivalent.

Env: PLANNER_DSN overrides .env; PLANNER_DB_PORT (default 5433) is read by init-env and compose;
PLANNER_ADMIN_IDLE_HOURS (default 8) ends idle admin sessions.
"""
import os
import sys


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else None
    if cmd == "init-env":
        from ai_project_planning_server import db
        values = db.write_env_file(os.environ.get("PLANNER_DB_PORT", "5433"))
        print(f"wrote {db.ENV_FILE} (PLANNER_DB_PASSWORD, PLANNER_DB_PORT={values['PLANNER_DB_PORT']}, PLANNER_DSN)")
    elif cmd == "bootstrap":
        from ai_project_planning_server.bootstrap import main as bootstrap_main
        bootstrap_main()
    elif cmd == "set-admin-password":
        from ai_project_planning_server.bootstrap import set_admin_password
        set_admin_password()
    elif cmd == "admin-login":
        from ai_project_planning_server.admin_cli import login
        sys.exit(login())
    elif cmd == "admin-logout":
        from ai_project_planning_server.admin_cli import logout
        sys.exit(logout())
    elif cmd is None:
        import uvicorn
        from ai_project_planning_server.tls import ensure_cert
        cert, key = ensure_cert()
        uvicorn.run("ai_project_planning_server.app:app", host=os.environ.get("PLANNER_HOST", "127.0.0.1"),
                    port=int(os.environ.get("PLANNER_PORT", "8787")), ssl_certfile=str(cert), ssl_keyfile=str(key))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
