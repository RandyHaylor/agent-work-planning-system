"""Startup order, run by the planner once per machine (steps 1-3 once; step 4 each session):

    uv run python -m server init-env    # 1. random DB password -> .env (gitignored); refuses to overwrite
    docker compose up -d --wait         # 2. Postgres, bound to 127.0.0.1, password from .env
    uv run python -m server bootstrap   # 3. schema + root tree; prints ADMIN_TOKEN once
    uv run python -m server             # 4. HTTPS on 127.0.0.1:8787 (PLANNER_HOST / PLANNER_PORT)

Env: PLANNER_DSN overrides .env; PLANNER_DB_PORT (default 5433) is read by init-env and compose.
"""
import os
import sys

cmd = sys.argv[1] if len(sys.argv) > 1 else None
if cmd == "init-env":
    from server import db
    values = db.write_env_file(os.environ.get("PLANNER_DB_PORT", "5433"))
    print(f"wrote {db.ENV_FILE} (PLANNER_DB_PASSWORD, PLANNER_DB_PORT={values['PLANNER_DB_PORT']}, PLANNER_DSN)")
elif cmd == "bootstrap":
    from server.bootstrap import main
    main()
elif cmd is None:
    import uvicorn
    from server.tls import ensure_cert
    cert, key = ensure_cert()
    uvicorn.run("server.app:app", host=os.environ.get("PLANNER_HOST", "127.0.0.1"), port=int(os.environ.get("PLANNER_PORT", "8787")),
                ssl_certfile=str(cert), ssl_keyfile=str(key))
else:
    raise SystemExit(__doc__)
