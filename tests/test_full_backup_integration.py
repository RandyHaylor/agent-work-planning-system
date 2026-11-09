"""Full encrypted backup, end to end, against the running server and Postgres.

Sets a task node done, finds the new backup file, decrypts it with the admin password, checks it is a
valid pg_dump archive, restores it into the test database, and confirms the node is still there.
Needs PLANNER_URL, PLANNER_ADMIN_PASSWORD and PLANNER_DSN (scripts/test_all.py sets all three).
"""
import os

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

BASE = os.environ.get("PLANNER_URL", "https://localhost:8787")
ADMIN_PASSWORD = os.environ.get("PLANNER_ADMIN_PASSWORD")
DSN = os.environ.get("PLANNER_DSN")
if not ADMIN_PASSWORD or not DSN:
    pytest.skip("PLANNER_ADMIN_PASSWORD and PLANNER_DSN not set", allow_module_level=True)

from ai_project_planning_server import db as _db  # noqa: E402
from ai_project_planning_server import full_backup as FB  # noqa: E402

ACCESS = {_db.ACCESS_HEADER: _db.read_access_token()}


def _client(token=None):
    headers = dict(ACCESS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=BASE, verify=False, headers=headers)


def test_task_done_takes_encrypted_backup_and_it_restores():
    with _client() as starter:
        workorder = starter.post("/workorders", json={"title": "backup workorder", "summary": "Backed up"}).json()
    planner = _client(workorder["planner_token"])
    task = planner.post("/nodes", json={"parent_id": workorder["node_id"], "title": "task to finish", "summary": "Finish me"}).json()
    marker_doc = planner.post(f"/nodes/{task['id']}/docs", json={"role": "instruction", "body": "unique marker 7f3a9c"}).json()

    before = {b.path for b in FB.list_backups()}
    r = planner.patch(f"/nodes/{task['id']}", json={"state": "done"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "full_backup" in body, body.get("full_backup_error")
    new = [b for b in FB.list_backups() if b.path not in before]
    assert len(new) == 1 and new[0].task_node_id == task["id"]
    path = new[0].path
    assert str(path) == body["full_backup"]
    assert FB.list_backups() == FB.list_backups(FB.backup_dir())

    # Decrypt with the admin password; wrong password fails; the dump is a real pg_dump archive.
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as conn:
        with pytest.raises(FB.FullBackupError):
            FB.decrypt_backup_file(conn, path, ADMIN_PASSWORD + "x")
        header, dump = FB.decrypt_backup_file(conn, path, ADMIN_PASSWORD)
    assert header.task_node_id == task["id"]
    assert dump.startswith(b"PGDMP")
    listing = FB.pg_restore_list(dump)
    assert "TABLE DATA" in listing and "nodes" in listing

    # Change something after the backup, restore, and confirm the database is back to the backup.
    planner.post(f"/nodes/{task['id']}/docs", json={"role": "report", "body": "written after the backup"})
    FB.restore(path, ADMIN_PASSWORD, force=True, dsn=DSN)
    node = planner.get(f"/nodes/{task['id']}")
    assert node.status_code == 200, node.text
    roles = [d["role"] for d in node.json()["docs"]]
    assert "instruction" in roles and "report" not in roles
    assert any(d["body"] == "unique marker 7f3a9c" for d in node.json()["docs"])
    assert node.json()["state"] == "done"
    # the server keeps working after a restore
    assert planner.get("/me").status_code == 200


def test_manual_backup_and_listing():
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as conn:
        path = FB.run_backup(conn, None)
    assert path.exists() and path.name.endswith("-task-manual.backup")
    assert any(b.path == path and b.task_node_id is None for b in FB.list_backups())
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as conn:
        header, dump = FB.decrypt_backup_file(conn, path, ADMIN_PASSWORD)
    assert header.task_node_id is None and dump.startswith(b"PGDMP")


def test_admin_password_change_keeps_backups_restorable():
    """The private key is re-encrypted when the password changes; an old backup still opens with the new password."""
    import subprocess
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as conn:
        path = FB.run_backup(conn, None)
    new_pw = ADMIN_PASSWORD + "-rotated"
    env = dict(os.environ, PLANNER_ADMIN_PASSWORD=new_pw, PLANNER_ADMIN_CURRENT_PASSWORD=ADMIN_PASSWORD)
    r = subprocess.run(["uv", "run", "ai-project-planning-server", "set-admin-password"], cwd=repo, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    try:
        with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as conn:
            header, dump = FB.decrypt_backup_file(conn, path, new_pw)
            assert dump.startswith(b"PGDMP")
            with pytest.raises(FB.FullBackupError):
                FB.decrypt_backup_file(conn, path, ADMIN_PASSWORD)
    finally:
        env = dict(os.environ, PLANNER_ADMIN_PASSWORD=ADMIN_PASSWORD, PLANNER_ADMIN_CURRENT_PASSWORD=new_pw)
        r = subprocess.run(["uv", "run", "ai-project-planning-server", "set-admin-password"], cwd=repo, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
