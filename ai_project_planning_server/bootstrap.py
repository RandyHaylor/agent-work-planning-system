"""Create schema, root tree (root -> kb, plans) and set the admin password.

Runs in one transaction: either the whole tree, meta and password exist afterwards, or nothing does.
A second run on a bootstrapped database is a no-op that says so.

No admin token is minted or printed. The admin is a session approved by the user through the
browser login (``uv run ai-project-planning-server admin-login``). The password is asked for interactively;
PLANNER_ADMIN_PASSWORD in the environment overrides the prompt, for tests and automation.

Also writes the server access token file (``server_access_token`` next to .env, or the path in
PLANNER_SERVER_ACCESS_TOKEN) and stores its hash: every request must carry it in X-Server-Access."""
import getpass
import os
import sys

from ai_project_planning_server import admin as A
from ai_project_planning_server import db


PASSWORD_WARNING = """
==================================================================
  WARNING: SAVE THIS PASSWORD SOMEWHERE SECURE. DO NOT FORGET IT.

  It is the only way to act as admin on this server. It is stored
  only as a hash and cannot be recovered or reset without it.
  Losing it means losing the ability to maintain the knowledge
  bases, manage project visibility, and apply proposed changes:
  important project information and documentation will become
  unreachable through the admin role.
==================================================================
"""


def read_password(purpose: str = "Admin password") -> str:
    env = os.environ.get("PLANNER_ADMIN_PASSWORD")
    if env is not None:
        print("warning: admin password taken from PLANNER_ADMIN_PASSWORD (non-interactive)", file=sys.stderr)
        problem = A.check_password_policy(env)
        if problem:
            raise SystemExit(problem)
        return env
    print(PASSWORD_WARNING)
    while True:
        pw = getpass.getpass(f"{purpose} (min {A.MIN_PASSWORD_LEN} chars): ")
        problem = A.check_password_policy(pw)
        if problem:
            print(problem)
            continue
        if getpass.getpass("Repeat: ") != pw:
            print("passwords do not match")
            continue
        return pw


def store_password(conn, password: str) -> None:
    salt, h = A.hash_password(password)
    for k, v in (("admin_pw_salt", salt), ("admin_pw_hash", h)):
        conn.execute("INSERT INTO meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (k, v))


def store_access_token(conn) -> str:
    """Write the server access token file and store its hash. Every request must carry the token."""
    token = db.write_access_token()
    conn.execute("INSERT INTO meta (key, value) VALUES ('server_access_hash', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (db.hash_token(token),))
    return token


def main():
    with db.connect() as conn:
        conn.execute("SELECT 1")  # fail early on a bad DSN before asking for a password
        db.apply_schema(conn)
        if db.meta_get(conn, "root_node_id"):
            if not db.meta_get(conn, "server_access_hash"):
                with conn.transaction():
                    store_access_token(conn)
                print(f"Server access token written to {db.access_token_path()}")
            print("Already bootstrapped. Use `uv run ai-project-planning-server set-admin-password` to change the admin password.")
            return
        password = read_password()
        with conn.transaction():
            store_access_token(conn)
            root = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (NULL, 'root') RETURNING id").fetchone()["id"]
            conn.execute("INSERT INTO docs (node_id, role, body) VALUES (%s, 'summary', 'Root of the planning tree.')", (root,))
            kb = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'kb') RETURNING id", (root,)).fetchone()["id"]
            conn.execute("INSERT INTO docs (node_id, role, body) VALUES (%s, 'summary', 'Knowledge bases: product, company, broader context. Each child is one kb. Read-only to agents; the admin applies approved changes.')", (kb,))
            plans = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'plans') RETURNING id", (root,)).fetchone()["id"]
            conn.execute("INSERT INTO docs (node_id, role, body) VALUES (%s, 'summary', 'All projects live beneath this node.')", (plans,))
            for k, v in (("root_node_id", root), ("kb_node_id", kb), ("plans_node_id", plans)):
                conn.execute("INSERT INTO meta (key, value) VALUES (%s, %s)", (k, str(v)))
            store_password(conn, password)
        print(f"root_node_id={root} kb_node_id={kb} plans_node_id={plans}")
        print(f"Server access token written to {db.access_token_path()} (every request carries it in {db.ACCESS_HEADER})")
        print("Admin password set. Become admin with: uv run ai-project-planning-server admin-login")
        print("Save the admin password somewhere secure now. It cannot be recovered.")


def set_admin_password():
    with db.connect() as conn:
        if not db.meta_get(conn, "root_node_id"):
            raise SystemExit("not bootstrapped: run `uv run ai-project-planning-server bootstrap` first")
        with conn.transaction():
            store_password(conn, read_password("New admin password"))
        print("Admin password updated. Existing admin sessions stay valid until the server restarts or they log out.")


if __name__ == "__main__":
    main()
