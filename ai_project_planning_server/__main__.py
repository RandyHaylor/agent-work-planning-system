"""Startup order, run by the planner once per machine (steps 1-3 once; step 4 each session):

    uv run ai-project-planning-server init-env            # 1. .env (gitignored, owner-only): DB password, DSN, server access token
    docker compose up -d --wait                           # 2. Postgres, bound to 127.0.0.1, password from .env
    uv run ai-project-planning-server bootstrap           # 3. schema + root tree; asks the user for the admin password
    uv run ai-project-planning-server                     # 4. HTTPS on 127.0.0.1:8787 (PLANNER_HOST / PLANNER_PORT)

Becoming admin (an agent runs this; the user types the password into the browser window it opens):

    uv run ai-project-planning-server admin-login         # prints ADMIN_TOKEN=adm_... once; dies with the server
    uv run ai-project-planning-server admin-logout        # ends the session in PLANNER_ADMIN_TOKEN
    uv run ai-project-planning-server set-admin-password  # change the password on an existing database

Full encrypted database backups (see full_backup.py; a backup is also taken whenever a task node is set done):

    uv run ai-project-planning-server backup              # dump + encrypt now, into PLANNER_FULL_BACKUP_DIR (default full_backups/)
    uv run ai-project-planning-server backups             # list backups with timestamp and task
    uv run ai-project-planning-server restore <file>      # asks for the admin password; replaces the database; server must be stopped
    uv run ai-project-planning-server init-backup-keys    # create the backup keypair on a database bootstrapped before backups existed

`python -m ai_project_planning_server <cmd>` is equivalent.

Starting a project needs no admin: anything holding the server access token may POST /projects and
receives that project's planner token.

Env: PLANNER_DSN and PLANNER_SERVER_ACCESS_TOKEN override the values in .env; PLANNER_DB_PORT (default
5433) is read by init-env and compose; PLANNER_ADMIN_IDLE_HOURS (default 8) ends idle admin sessions.
"""
import os
import sys


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else None
    if cmd == "init-env":
        from ai_project_planning_server import db
        values = db.write_env_file(os.environ.get("PLANNER_DB_PORT", "5433"))
        print(f"wrote {db.ENV_FILE} (PLANNER_DB_PASSWORD, PLANNER_DB_PORT={values['PLANNER_DB_PORT']}, PLANNER_DSN, {db.ACCESS_KEY}); owner-only")
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
    elif cmd == "backup":
        from ai_project_planning_server import full_backup
        sys.exit(full_backup.cli_backup())
    elif cmd == "backups":
        from ai_project_planning_server import full_backup
        sys.exit(full_backup.cli_backups())
    elif cmd == "restore":
        from ai_project_planning_server import full_backup
        sys.exit(full_backup.cli_restore(args[1:]))
    elif cmd == "init-backup-keys":
        from ai_project_planning_server import full_backup
        sys.exit(full_backup.cli_init_keys())
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
