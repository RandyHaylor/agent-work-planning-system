"""Real integration tests over HTTPS against the running server and Postgres.

Requires: docker compose up, bootstrap done with PLANNER_ADMIN_PASSWORD, server running with
PLANNER_TEST_HOOKS=1 and a short PLANNER_ADMIN_FAIL_WINDOW (scripts/test_all.py does all of this).
The admin session is obtained through the real login flow: nonce, password form, pickup.
"""
import os
import time

import httpx
import pytest

BASE = os.environ.get("PLANNER_URL", "https://localhost:8787")
ADMIN_PASSWORD = os.environ.get("PLANNER_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    pytest.skip("PLANNER_ADMIN_PASSWORD not set", allow_module_level=True)

from ai_project_planning_server import db as _db  # noqa: E402

ACCESS = {_db.ACCESS_HEADER: _db.read_access_token()}  # every request carries the server access token


def client(token):
    return httpx.Client(base_url=BASE, verify=False, headers={**ACCESS, "Authorization": f"Bearer {token}"})


def anon():
    """Access token, no bearer: enough to create a project, nothing else."""
    return httpx.Client(base_url=BASE, verify=False, headers=ACCESS)


def bare(token=None):
    """No access token at all: every request must be refused before any other auth."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(base_url=BASE, verify=False, headers=headers)


def admin_login(password=ADMIN_PASSWORD):
    """What `uv run ai-project-planning-server admin-login` plus the user's browser do, programmatically.
    The nonce is registered with the access token; the browser page and form need only the nonce."""
    with anon() as c, bare() as browser:
        nonce = c.post("/admin/nonce").json()["nonce"]
        assert c.get(f"/admin/session/{nonce}").status_code == 404  # nothing to pick up before approval
        r = browser.post("/admin/login", data={"nonce": nonce, "password": password})
        if r.status_code != 200:
            return r, None
        got = c.get(f"/admin/session/{nonce}")
        assert got.status_code == 200
        return r, got.json()["token"]


@pytest.fixture(scope="module")
def admin():
    _, token = admin_login()
    assert token and token.startswith("adm_")
    return client(token)


@pytest.fixture(scope="module")
def world(admin):
    """root -> plans -> project A (planner A, task, worker) ; project B (planner B)
                -> kb    -> kb Product (assigned to A) ; kb Company (not assigned)
    """
    me = admin.get("/me").json()
    tree = admin.get(f"/nodes/{me['scope_node_id']}/tree").json()
    kids = {c["title"]: c["id"] for c in tree["children"]}
    plans, kb = kids["plans"], kids["kb"]
    # Projects are started with the access token alone: no admin involved.
    with anon() as starter:
        pa = starter.post("/projects", json={"title": "project A", "summary": "Project A"}).json()
        pb = starter.post("/projects", json={"title": "project B", "summary": "Project B"}).json()
    kb_prod = admin.post("/kbs", json={"title": "Product", "summary": "What the product is"}).json()
    kb_co = admin.post("/kbs", json={"title": "Company", "summary": "Who we are"}).json()
    planner, planner_b = client(pa["planner_token"]), client(pb["planner_token"])
    planner.patch(f"/projects/{pa['uuid']}", json={"kbs": [kb_prod["uuid"]]})  # the planner picks its workers' kbs
    project = admin.get(f"/nodes/{pa['node_id']}").json()
    other = admin.get(f"/nodes/{pb['node_id']}").json()
    env = planner.post(f"/nodes/{project['id']}/docs", json={"role": "environment", "body": "Stack: Python 3.12, stdlib only."}).json()
    task = planner.post("/nodes", json={"parent_id": project["id"], "title": "task 1", "summary": "Build module X"}).json()
    instr = planner.post(f"/nodes/{task['id']}/docs", json={"role": "instruction", "body": "Interfaces: ... DoD: ..."}).json()
    worker_tok = planner.post("/tokens", json={"label": "worker", "scope_node_id": task["id"], "role": "worker"}).json()
    worker = client(worker_tok["token"])
    return dict(admin=admin, planner=planner, planner_b=planner_b, worker=worker, plans=plans, kb=kb, project=project, other=other,
                pa=pa, pb=pb, kb_prod=kb_prod, kb_co=kb_co, task=task, instr=instr, env=env, worker_tok=worker_tok, root_node=me["scope_node_id"])


def test_401_without_token():
    assert anon().get("/me").status_code == 401
    assert client("pln_bogus").get("/me").status_code == 401
    assert client("adm_bogus").get("/me").status_code == 401


def test_401_without_server_access_token(world):
    """The access token is checked before anything else: a valid bearer without it is still refused."""
    for tok in (world["worker_tok"]["token"], world["pa"]["planner_token"]):
        with bare(tok) as b:
            for path in ("/me", "/projects", "/kbs", f"/nodes/{world['task']['id']}", "/escalations", "/tokens"):
                assert b.get(path).status_code == 401, path
            assert b.post("/projects", json={"title": "x", "summary": "x"}).status_code == 401
            assert b.post(f"/nodes/{world['task']['id']}/docs", json={"role": "report", "body": "x"}).status_code == 401
    with bare() as b:
        assert b.post("/projects", json={"title": "x", "summary": "x"}).status_code == 401
        assert b.post("/admin/nonce").status_code == 401
        assert b.get("/admin/session/anything").status_code == 401
    with httpx.Client(base_url=BASE, verify=False, headers={_db.ACCESS_HEADER: "acc_wrong"}) as b:
        assert b.post("/projects", json={"title": "x", "summary": "x"}).status_code == 401


def test_admin_login_page_and_nonce_rules():
    with anon() as c, bare() as browser:
        assert browser.get("/admin/login?nonce=bogus").status_code == 404
        nonce = c.post("/admin/nonce").json()["nonce"]
        page = browser.get(f"/admin/login?nonce={nonce}")  # the browser carries no header: the nonce is the proof
        assert page.status_code == 200 and 'name="password"' in page.text and nonce in page.text
        # an unregistered nonce cannot log in, even with the right password
        assert browser.post("/admin/login", data={"nonce": "forged", "password": ADMIN_PASSWORD}).status_code == 404


def test_admin_session_single_pickup_and_logout(admin):
    r, token = admin_login()
    assert r.status_code == 200 and "close this window" in r.text
    a = client(token)
    assert a.get("/me").json()["role"] == "admin"
    # the nonce was consumed: the login page for it is gone and the token cannot be picked up twice
    assert a.post("/admin/logout").status_code == 204
    assert a.get("/me").status_code == 401
    assert a.post("/admin/logout").status_code == 401


def test_admin_session_does_not_survive_restart(admin):
    """PLANNER_TEST_HOOKS exposes what a restart does: the in-memory store is cleared."""
    _, token = admin_login()
    a = client(token)
    assert a.get("/me").status_code == 200
    assert a.post("/admin/_clear_sessions").status_code == 204
    assert a.get("/me").status_code == 401
    assert admin.get("/me").status_code == 401  # the module's admin died too
    # re-login works, and the module fixture client is repointed for the remaining tests
    _, token2 = admin_login()
    admin.headers["Authorization"] = f"Bearer {token2}"
    assert admin.get("/me").status_code == 200


def test_admin_wrong_password_rejected_then_rate_limited():
    r, token = admin_login("not the password")
    assert r.status_code == 401 and token is None and "Wrong password" in r.text
    with anon() as c, bare() as browser:
        for _ in range(4):
            nonce = c.post("/admin/nonce").json()["nonce"]
            assert browser.post("/admin/login", data={"nonce": nonce, "password": "still wrong"}).status_code == 401
        nonce = c.post("/admin/nonce").json()["nonce"]
        assert browser.post("/admin/login", data={"nonce": nonce, "password": ADMIN_PASSWORD}).status_code == 429
    # the runner sets PLANNER_ADMIN_FAIL_WINDOW=3 so the lockout clears quickly
    time.sleep(float(os.environ.get("PLANNER_ADMIN_FAIL_WINDOW", "60")) + 0.5)
    _, token = admin_login()
    assert token
    client(token).post("/admin/logout")


def test_admin_is_never_a_token(admin, world):
    assert world["planner"].post("/tokens", json={"label": "x", "scope_node_id": world["task"]["id"], "role": "admin"}).status_code == 422
    assert admin.post("/tokens", json={"label": "x", "scope_node_id": world["root_node"], "role": "admin"}).status_code == 422
    assert all(t["role"] in ("planner", "worker") for t in admin.get("/tokens").json())


def test_me_reports_role_and_project(world):
    w = world["worker"].get("/me").json()
    assert w["scope_node_id"] == world["task"]["id"] and w["role"] == "worker" and w["project_uuid"] == world["pa"]["uuid"]
    p = world["planner"].get("/me").json()
    assert p["role"] == "planner" and p["project_node_id"] == world["project"]["id"]
    a = world["admin"].get("/me").json()
    assert a["role"] == "admin" and a["project_uuid"] is None and a["token_id"] is None


def test_project_creation_returns_working_planner_token(world):
    """Starting a project needs no admin: the access token alone, a planner, or the admin. Not a worker."""
    pa = world["pa"]
    assert set(pa) >= {"uuid", "node_id", "planner_token", "planner_token_id", "kbs", "visible"}
    assert pa["visible"] is True and len(pa["uuid"]) == 36
    assert world["planner"].get(f"/nodes/{pa['node_id']}").json()["uuid"] == pa["uuid"]
    with anon() as starter:
        r = starter.post("/projects", json={"title": "started with access only", "summary": "x"})
        assert r.status_code == 201 and client(r.json()["planner_token"]).get("/me").json()["role"] == "planner"
        assert starter.get("/projects").status_code == 401  # access alone reads nothing
    r = world["planner"].post("/projects", json={"title": "started by a planner", "summary": "x"})
    assert r.status_code == 201 and r.json()["visible"] is True
    assert world["admin"].post("/projects", json={"title": "started by admin", "summary": "x"}).status_code == 201
    assert world["worker"].post("/projects", json={"title": "x", "summary": "x"}).status_code == 403
    listed = {p["uuid"]: p for p in world["admin"].get("/projects").json()}
    assert listed[pa["uuid"]]["kbs"] == [world["kb_prod"]["uuid"]]


def test_node_has_summary_and_instruction(world):
    n = world["worker"].get(f"/nodes/{world['task']['id']}").json()
    assert sorted(d["role"] for d in n["docs"]) == ["instruction", "summary"]


def test_worker_404_on_ancestors_and_siblings(world):
    w = world["worker"]
    assert w.get(f"/nodes/{world['project']['id']}").status_code == 404
    assert w.get(f"/nodes/{world['plans']}").status_code == 404
    assert w.get(f"/nodes/{world['root_node']}").status_code == 404
    assert w.get(f"/nodes/{world['other']['id']}").status_code == 404
    assert w.get(f"/nodes/{world['project']['id']}/tree").status_code == 404


def test_kb_assignment_rules(world):
    """A planner reads every kb and picks which ones its workers see; workers read only those; nobody but admin writes a kb."""
    p, w, a = world["planner"], world["worker"], world["admin"]
    prod, co = world["kb_prod"]["node_id"], world["kb_co"]["node_id"]
    assert p.get(f"/nodes/{prod}").status_code == 200 and w.get(f"/nodes/{prod}").status_code == 200
    assert p.get(f"/nodes/{co}").status_code == 200  # unassigned to its project, still readable by the planner
    assert w.get(f"/nodes/{co}").status_code == 404
    both = {world["kb_prod"]["uuid"], world["kb_co"]["uuid"]}
    assert {k["uuid"] for k in p.get("/kbs").json()} == both
    assert [k["uuid"] for k in w.get("/kbs").json()] == [world["kb_prod"]["uuid"]]
    assert {k["uuid"] for k in a.get("/kbs").json()} == both
    assert {c["id"] for c in p.get(f"/nodes/{world['kb']}").json()["children"]} == {prod, co}
    assert w.get(f"/nodes/{world['kb']}").status_code == 404
    # the kb set is the planner's call for its own project only; visibility stays the admin's
    assert world["planner_b"].patch(f"/projects/{world['pa']['uuid']}", json={"kbs": [world["kb_co"]["uuid"]]}).status_code == 403
    assert p.patch(f"/projects/{world['pb']['uuid']}", json={"kbs": [world["kb_co"]["uuid"]]}).status_code == 403
    assert w.patch(f"/projects/{world['pa']['uuid']}", json={"kbs": [world["kb_co"]["uuid"]]}).status_code in (403, 404)
    assert p.patch(f"/projects/{world['pa']['uuid']}", json={"visible": False}).status_code == 403
    # admin writes; planner and worker never do, not even on an assigned kb
    page = a.post("/nodes", json={"parent_id": prod, "title": "Glossary", "summary": "terms"})
    assert page.status_code == 201
    assert a.post(f"/nodes/{prod}/docs", json={"role": "instruction", "body": "x"}).status_code == 201
    assert p.get(f"/nodes/{page.json()['id']}").status_code == 200
    for who in (p, w):
        assert who.post(f"/nodes/{prod}/docs", json={"role": "report", "body": "x"}).status_code == 403
        assert who.post("/nodes", json={"parent_id": prod, "title": "w", "summary": "s"}).status_code == 403
        assert who.post("/kbs", json={"title": "x", "summary": "x"}).status_code == 403
    # proposals are written on the agent's own node
    assert w.post(f"/nodes/{world['task']['id']}/docs", json={"role": "kb_proposal", "body": "Add: ..."}).status_code == 201
    assert p.post(f"/nodes/{world['project']['id']}/docs", json={"role": "kb_proposal", "body": "Add: ..."}).status_code == 201
    # reassignment by the planner takes effect for its workers at once
    assert p.patch(f"/projects/{world['pa']['uuid']}", json={"kbs": [world["kb_prod"]["uuid"], world["kb_co"]["uuid"]]}).status_code == 200
    assert w.get(f"/nodes/{co}").status_code == 200
    assert p.patch(f"/projects/{world['pa']['uuid']}", json={"kbs": [world["kb_prod"]["uuid"]]}).status_code == 200
    assert w.get(f"/nodes/{co}").status_code == 404


def test_node_level_kb_override_for_workers(world):
    """A planner can narrow or widen the kb set for workers at or beneath one node; nearest override wins."""
    p, w, tid = world["planner"], world["worker"], world["task"]["id"]
    prod, co = world["kb_prod"], world["kb_co"]
    assert w.get(f"/nodes/{prod['node_id']}").status_code == 200 and w.get(f"/nodes/{co['node_id']}").status_code == 404
    assert w.patch(f"/nodes/{tid}", json={"kbs": [co["uuid"]]}).status_code == 403
    assert world["planner_b"].patch(f"/nodes/{tid}", json={"kbs": [co["uuid"]]}).status_code == 403
    r = p.patch(f"/nodes/{tid}", json={"kbs": [co["uuid"]]})
    assert r.status_code == 200 and r.json()["kbs"] == [co["uuid"]]
    assert w.get(f"/nodes/{co['node_id']}").status_code == 200 and w.get(f"/nodes/{prod['node_id']}").status_code == 404
    assert [k["uuid"] for k in w.get("/kbs").json()] == [co["uuid"]]
    # a worker scoped beneath the overridden node inherits the override
    sub = p.post("/nodes", json={"parent_id": tid, "title": "sub task", "summary": "s"}).json()
    sub_tok = p.post("/tokens", json={"label": "sub-w", "scope_node_id": sub["id"], "role": "worker"}).json()
    with client(sub_tok["token"]) as sw:
        assert [k["uuid"] for k in sw.get("/kbs").json()] == [co["uuid"]]
        # a nearer override on the sub node wins over the task's
        assert p.patch(f"/nodes/{sub['id']}", json={"kbs": []}).status_code == 200
        assert sw.get("/kbs").json() == [] and sw.get(f"/nodes/{co['node_id']}").status_code == 404
    assert [k["uuid"] for k in w.get("/kbs").json()] == [co["uuid"]]  # the task's own override unchanged
    # an override on the task equal to the project set restores the default view for the rest of the suite
    assert p.patch(f"/nodes/{tid}", json={"kbs": [prod["uuid"]]}).status_code == 200
    assert w.get(f"/nodes/{prod['node_id']}").status_code == 200 and w.get(f"/nodes/{co['node_id']}").status_code == 404
    assert p.patch(f"/nodes/{world['kb_prod']['node_id']}", json={"kbs": []}).status_code in (403, 422)


def test_worker_sees_ancestor_environment_doc(world):
    n = world["worker"].get(f"/nodes/{world['task']['id']}").json()
    assert [e["id"] for e in n["environment"]] == [world["env"]["id"]]
    assert n["environment"][0]["body"].startswith("Stack:")
    assert all(d["role"] != "environment" for d in n["docs"])


def test_planner_reads_visible_sibling_project_but_cannot_write(world):
    p, other = world["planner"], world["other"]
    assert p.get(f"/nodes/{world['root_node']}").status_code == 200
    assert p.get(f"/nodes/{other['id']}").status_code == 200
    assert p.get(f"/nodes/{other['id']}/tree").status_code == 200
    titles = {c["title"] for c in p.get(f"/nodes/{world['plans']}/tree").json()["children"]}
    assert {"project A", "project B"} <= titles
    assert p.post(f"/nodes/{other['id']}/docs", json={"role": "question", "body": "x"}).status_code == 403
    assert p.post("/nodes", json={"parent_id": other["id"], "title": "x", "summary": "x"}).status_code == 403
    assert p.patch(f"/nodes/{other['id']}", json={"state": "blocked"}).status_code == 403
    assert p.post("/nodes", json={"parent_id": world["plans"], "title": "x", "summary": "x"}).status_code == 403


def test_hidden_project_until_admin_grants_visibility(world):
    a, pa, pb = world["admin"], world["planner"], world["planner_b"]
    hidden = a.post("/projects", json={"title": "secret", "summary": "hush"}).json()
    hp = client(hidden["planner_token"])
    assert pa.get(f"/nodes/{hidden['node_id']}").status_code == 200  # visible by default
    assert hp.patch(f"/projects/{hidden['uuid']}", json={"visible": False}).status_code == 403  # its own planner cannot hide it
    r = a.patch(f"/projects/{hidden['uuid']}", json={"visible": False})
    assert r.status_code == 200 and r.json()["visible"] is False
    assert pa.get(f"/nodes/{hidden['node_id']}").status_code == 404
    assert pb.get(f"/nodes/{hidden['node_id']}").status_code == 404
    assert hidden["uuid"] not in {p["uuid"] for p in pa.get("/projects").json()}
    assert "secret" not in {c["title"] for c in pa.get(f"/nodes/{world['plans']}/tree").json()["children"]}
    assert "secret" not in {c["title"] for c in pa.get(f"/nodes/{world['plans']}").json()["children"]}
    assert hp.get(f"/nodes/{hidden['node_id']}").status_code == 200  # its own planner always
    assert pa.post(f"/projects/{hidden['uuid']}/visibility", json={"viewer": world["pa"]["uuid"]}).status_code == 403
    assert a.post(f"/projects/{hidden['uuid']}/visibility", json={"viewer": world["pa"]["uuid"]}).status_code == 201
    assert pa.get(f"/nodes/{hidden['node_id']}").status_code == 200
    assert pa.get(f"/nodes/{hidden['node_id']}/tree").status_code == 200
    assert pb.get(f"/nodes/{hidden['node_id']}").status_code == 404
    assert pa.post(f"/nodes/{hidden['node_id']}/docs", json={"role": "question", "body": "x"}).status_code == 403
    assert a.delete(f"/projects/{hidden['uuid']}/visibility/{world['pa']['uuid']}").status_code == 204
    assert pa.get(f"/nodes/{hidden['node_id']}").status_code == 404
    assert a.patch("/projects/00000000-0000-0000-0000-000000000000", json={"visible": True}).status_code == 404
    assert a.patch(f"/projects/{hidden['uuid']}", json={}).status_code == 422


def test_tree(world):
    t = world["planner"].get(f"/nodes/{world['project']['id']}/tree").json()
    assert t["children"][0]["id"] == world["task"]["id"]
    assert "docs" not in t


def test_planner_writes_on_project_node_it_did_not_create(world):
    """Admin created the project; the planner must still log questions, write instructions, set state there."""
    pid = world["project"]["id"]
    r = world["planner"].post(f"/nodes/{pid}/docs", json={"role": "question", "body": "From node / Question / Answer / Answered by / Scope"})
    assert r.status_code == 201
    assert world["planner"].post(f"/nodes/{pid}/docs", json={"role": "instruction", "body": "plan of record"}).status_code == 201
    assert world["planner"].patch(f"/nodes/{pid}", json={"state": "blocked"}).status_code == 200
    assert world["planner"].patch(f"/nodes/{pid}", json={"state": "open"}).status_code == 200


def test_planner_edits_any_doc_in_project(world):
    assert world["planner"].patch(f"/docs/{world['instr']['id']}", json={"body": "revised by planner"}).status_code == 200
    summary = [d for d in world["planner"].get(f"/nodes/{world['project']['id']}").json()["docs"] if d["role"] == "summary"][0]
    assert world["planner"].patch(f"/docs/{summary['id']}", json={"body": "edited summary (admin-authored)"}).status_code == 200


def test_worker_cannot_write_planner_roles(world):
    w, tid = world["worker"], world["task"]["id"]
    for role in ("instruction", "summary", "environment", "question", "survey", "approval", "review"):
        assert w.post(f"/nodes/{tid}/docs", json={"role": role, "body": "x"}).status_code == 403, role
    assert w.patch(f"/docs/{world['instr']['id']}", json={"body": "hacked"}).status_code == 403
    assert w.patch(f"/nodes/{tid}", json={"state": "done"}).status_code == 403


def test_worker_writes_report_and_edits_own_only(world):
    w, tid = world["worker"], world["task"]["id"]
    r = w.post(f"/nodes/{tid}/docs", json={"role": "report", "body": "built it"})
    assert r.status_code == 201
    assert w.patch(f"/docs/{r.json()['id']}", json={"body": "built it, proven"}).status_code == 200
    pr = world["planner"].post(f"/nodes/{tid}/docs", json={"role": "report", "body": "planner note"}).json()
    assert w.patch(f"/docs/{pr['id']}", json={"body": "nope"}).status_code == 403


def test_worker_creates_child_but_cannot_plan_it(world):
    w, tid = world["worker"], world["task"]["id"]
    child = w.post("/nodes", json={"parent_id": tid, "title": "sub", "summary": "sub summary"})
    assert child.status_code == 201
    cid = child.json()["id"]
    assert w.get(f"/nodes/{cid}").status_code == 200
    assert w.post(f"/nodes/{cid}/docs", json={"role": "report", "body": "sub report"}).status_code == 201
    assert w.post(f"/nodes/{cid}/docs", json={"role": "instruction", "body": "sub instr"}).status_code == 403
    assert w.patch(f"/nodes/{cid}", json={"state": "done"}).status_code == 403
    summary = [d for d in w.get(f"/nodes/{cid}").json()["docs"] if d["role"] == "summary"][0]
    assert w.patch(f"/docs/{summary['id']}", json={"body": "sub summary, revised"}).status_code == 200
    assert w.patch(f"/docs/{world['instr']['id']}", json={"body": "nope"}).status_code == 403


def test_worker_cannot_create_outside_scope(world):
    assert world["worker"].post("/nodes", json={"parent_id": world["project"]["id"], "title": "x", "summary": "x"}).status_code == 404
    assert world["planner_b"].post("/nodes", json={"parent_id": world["plans"], "title": "x", "summary": "x"}).status_code == 403


def test_state_planner_only(world):
    tid = world["task"]["id"]
    assert world["worker"].patch(f"/nodes/{tid}", json={"state": "blocked"}).status_code == 403
    assert world["planner"].patch(f"/nodes/{tid}", json={"state": "blocked"}).status_code == 200
    assert world["planner"].patch(f"/nodes/{tid}", json={"state": "bogus"}).status_code == 422


def test_escalation_flow(world):
    w, p, tid = world["worker"], world["planner"], world["task"]["id"]
    e = w.post(f"/nodes/{tid}/docs", json={"role": "escalation", "body": "Interface Y is ambiguous"}).json()
    assert any(x["id"] == e["id"] for x in p.get("/escalations").json())
    assert any(x["id"] == e["id"] for x in world["admin"].get("/escalations").json())
    assert w.patch(f"/docs/{e['id']}", json={"answer": "self-answer"}).status_code == 403
    assert world["planner_b"].patch(f"/docs/{e['id']}", json={"answer": "not mine"}).status_code == 403
    r = p.patch(f"/docs/{e['id']}", json={"answer": "Use Z", "resolved": True})
    assert r.status_code == 200 and r.json()["answer"] == "Use Z"
    assert all(x["id"] != e["id"] for x in p.get("/escalations").json())


def test_survey_approval_review_planner_only_worker_reads(world):
    p, w, tid = world["planner"], world["worker"], world["task"]["id"]
    ids = {}
    for role in ("survey", "approval", "review"):
        r = p.post(f"/nodes/{tid}/docs", json={"role": role, "body": f"{role} body"})
        assert r.status_code == 201, role
        ids[role] = r.json()["id"]
        assert w.post(f"/nodes/{tid}/docs", json={"role": role, "body": "x"}).status_code == 403, role
        assert w.patch(f"/docs/{ids[role]}", json={"body": "hacked"}).status_code == 403, role
    docs = w.get(f"/nodes/{tid}").json()["docs"]
    approval = [d for d in docs if d["role"] == "approval"]
    assert approval and approval[0]["body"] == "approval body"
    assert p.patch(f"/docs/{ids['review']}", json={"body": "edited"}).status_code == 200


def test_mint_rules(world):
    w, p, a = world["worker"], world["planner"], world["admin"]
    tid, pid = world["task"]["id"], world["project"]["id"]
    assert w.post("/tokens", json={"label": "x", "scope_node_id": tid, "role": "worker"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": tid, "role": "bogus"}).status_code == 422
    # a planner mints workers inside its project only, and never planners or admins
    assert p.post("/tokens", json={"label": "x", "scope_node_id": pid, "role": "planner"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": tid, "role": "admin"}).status_code == 422
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["other"]["id"], "role": "worker"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["kb_prod"]["node_id"], "role": "worker"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": tid, "role": "worker"}).status_code == 201
    # admin mints planners for a project, workers anywhere in a project, never a planner outside one
    assert a.post("/tokens", json={"label": "p2", "scope_node_id": pid, "role": "planner"}).status_code == 201
    assert a.post("/tokens", json={"label": "x", "scope_node_id": world["plans"], "role": "planner"}).status_code == 403
    assert a.post("/tokens", json={"label": "x", "scope_node_id": world["kb_prod"]["node_id"], "role": "worker"}).status_code == 403


def test_revoke_rules(world):
    p, w, a = world["planner"], world["worker"], world["admin"]
    t = p.post("/tokens", json={"label": "tmp", "scope_node_id": world["task"]["id"], "role": "worker"}).json()
    assert w.delete(f"/tokens/{t['token_id']}").status_code == 403
    # project B's planner can see project A but not revoke inside it
    assert world["planner_b"].delete(f"/tokens/{t['token_id']}").status_code == 403
    # admin did not mint it: still allowed
    assert a.delete(f"/tokens/{t['token_id']}").status_code == 204
    assert client(t["token"]).get("/me").status_code == 401
    t2 = p.post("/tokens", json={"label": "tmp2", "scope_node_id": world["task"]["id"], "role": "worker"}).json()
    assert p.delete(f"/tokens/{t2['token_id']}").status_code == 204
    assert p.delete(f"/tokens/{world['pa']['planner_token_id']}").status_code == 409


def test_revoke_cascades_through_minting_chain(world):
    a = world["admin"]
    sub = a.post("/tokens", json={"label": "sub-pl", "scope_node_id": world["project"]["id"], "role": "planner"}).json()
    grand = client(sub["token"]).post("/tokens", json={"label": "grand-w", "scope_node_id": world["task"]["id"], "role": "worker"}).json()
    assert client(grand["token"]).get("/me").status_code == 200
    assert a.delete(f"/tokens/{sub['token_id']}").status_code == 204
    assert client(sub["token"]).get("/me").status_code == 401
    assert client(grand["token"]).get("/me").status_code == 401
    listed = {t["id"]: t for t in a.get("/tokens").json()}
    assert listed[sub["token_id"]]["revoked"] is True and listed[sub["token_id"]]["active"] is False
    assert listed[grand["token_id"]]["revoked"] is False  # own flag untouched
    assert listed[grand["token_id"]]["active"] is False   # but dead through the chain
    assert listed[world["worker_tok"]["token_id"]]["active"] is True


def test_retrieve_secret(world):
    p, w, a = world["planner"], world["worker"], world["admin"]
    # the secret retrieved equals the one issued at mint, and it works
    wt = world["worker_tok"]
    got = p.get(f"/tokens/{wt['token_id']}/secret")
    assert got.status_code == 200 and got.json() == {"token_id": wt["token_id"], "token": wt["token"]}
    assert client(got.json()["token"]).get("/me").json()["scope_node_id"] == world["task"]["id"]
    # admin retrieves a planner's token and it works
    pb = world["pb"]
    got = a.get(f"/tokens/{pb['planner_token_id']}/secret")
    assert got.status_code == 200 and got.json()["token"] == pb["planner_token"]
    assert client(got.json()["token"]).get("/me").json()["scope_node_id"] == pb["node_id"]
    # planner retrieves its own
    me = p.get("/me").json()
    assert p.get(f"/tokens/{me['token_id']}/secret").status_code == 200
    # planner 403 on a sibling project's planner token and on a sibling planner in its own project
    assert p.get(f"/tokens/{pb['planner_token_id']}/secret").status_code == 403
    sub = a.post("/tokens", json={"label": "sub-pl3", "scope_node_id": world["project"]["id"], "role": "planner"}).json()
    assert p.get(f"/tokens/{sub['token_id']}/secret").status_code == 403
    assert a.get(f"/tokens/{sub['token_id']}/secret").json()["token"] == sub["token"]
    # worker: 403, even for itself
    assert w.get(f"/tokens/{wt['token_id']}/secret").status_code == 403
    # revoked: 409; unknown: 404
    assert a.delete(f"/tokens/{sub['token_id']}").status_code == 204
    assert a.get(f"/tokens/{sub['token_id']}/secret").status_code == 409
    assert a.get("/tokens/999999/secret").status_code == 404


def test_rotate_rules_and_effect(world):
    p, w, a = world["planner"], world["worker"], world["admin"]
    t = p.post("/tokens", json={"label": "rot", "scope_node_id": world["task"]["id"], "role": "worker"}).json()
    before = {x["id"]: x for x in p.get("/tokens").json()}[t["token_id"]]
    assert before["rotated_at"] is None
    # worker: never, not even itself
    assert w.post(f"/tokens/{world['worker_tok']['token_id']}/rotate").status_code == 403
    assert w.post(f"/tokens/{t['token_id']}/rotate").status_code == 403
    # project B's planner can see project A's token but cannot rotate it
    assert world["planner_b"].post(f"/tokens/{t['token_id']}/rotate").status_code == 403
    # project A's planner rotates its own worker: same id, scope, parent; old plaintext dead, new one works
    r = p.post(f"/tokens/{t['token_id']}/rotate")
    assert r.status_code == 201
    new = r.json()
    assert new["token_id"] == t["token_id"] and new["scope_node_id"] == world["task"]["id"] and new["role"] == "worker"
    assert new["token"] != t["token"]
    assert client(t["token"]).get("/me").status_code == 401
    assert client(new["token"]).get("/me").json()["scope_node_id"] == world["task"]["id"]
    after = {x["id"]: x for x in p.get("/tokens").json()}[t["token_id"]]
    assert after["parent_token_id"] == before["parent_token_id"] and after["rotated_at"] is not None
    assert after["revoked"] is False and after["active"] is True
    # retrieve now returns the rotated plaintext
    assert p.get(f"/tokens/{t['token_id']}/secret").json()["token"] == new["token"]
    # a planner rotates its own token; the old planner plaintext dies
    me = p.get("/me").json()
    r = p.post(f"/tokens/{me['token_id']}/rotate")
    assert r.status_code == 201
    old_header = p.headers["Authorization"]
    p.headers["Authorization"] = f"Bearer {r.json()['token']}"
    assert p.get("/me").json()["token_id"] == me["token_id"]
    assert client(old_header[7:]).get("/me").status_code == 401
    # a planner cannot rotate another planner's token in its own project; the admin can
    sub = a.post("/tokens", json={"label": "sub-pl2", "scope_node_id": world["project"]["id"], "role": "planner"}).json()
    assert p.post(f"/tokens/{sub['token_id']}/rotate").status_code == 403
    assert a.post(f"/tokens/{sub['token_id']}/rotate").status_code == 201
    # revoked tokens are not rotated; cascade is untouched by rotation
    assert a.delete(f"/tokens/{sub['token_id']}").status_code == 204
    assert a.post(f"/tokens/{sub['token_id']}/rotate").status_code == 409
    # unknown token: 404
    assert a.post("/tokens/999999/rotate").status_code == 404


def test_list_tokens(world):
    p, w, a = world["planner"], world["worker"], world["admin"]
    assert w.get("/tokens").status_code == 403
    mine = {t["id"] for t in p.get("/tokens").json()}
    assert world["pa"]["planner_token_id"] in mine and world["worker_tok"]["token_id"] in mine
    assert world["pb"]["planner_token_id"] not in mine
    everything = {t["id"] for t in a.get("/tokens").json()}
    assert world["pb"]["planner_token_id"] in everything and world["worker_tok"]["token_id"] in everything


def _backup_dir():
    d = os.environ.get("PLANNER_BACKUP_DIR")
    if not d:
        pytest.skip("PLANNER_BACKUP_DIR not set")
    from pathlib import Path
    return Path(d)


def test_backup_written_on_every_write(world):
    import json
    base = _backup_dir()
    pid, tid = world["project"]["id"], world["task"]["id"]
    proj_dir = base / world["pa"]["uuid"]
    assert (proj_dir / "title").read_text(encoding="utf-8") == "project A\n"
    tree = {n["id"]: n for n in json.loads((proj_dir / "tree.json").read_text())}
    assert pid in tree and tid in tree and tree[tid]["parent_id"] == pid and tree[pid]["uuid"] == world["pa"]["uuid"]
    r = world["worker"].post(f"/nodes/{tid}/docs", json={"role": "report", "body": "first draft "}).json()
    f = proj_dir / "docs" / f"{tid}-report-{r['id']}.md"
    assert f.exists()
    assert f.read_text(encoding="utf-8").endswith("\n\nfirst draft ")
    assert "author: worker" in f.read_text(encoding="utf-8")
    # the project was started with the access token (no bearer): no author token, rendered as "admin"
    summary = next(p for p in (proj_dir / "docs").iterdir() if p.name.startswith(f"{pid}-summary-"))
    assert "author: admin" in summary.read_text(encoding="utf-8")
    world["worker"].patch(f"/docs/{r['id']}", json={"body": "second draft"})
    assert f.read_text(encoding="utf-8").endswith("\n\nsecond draft")
    e = world["worker"].post(f"/nodes/{tid}/docs", json={"role": "escalation", "body": "q"}).json()
    world["planner"].patch(f"/docs/{e['id']}", json={"answer": "a", "resolved": True})
    ef = (proj_dir / "docs" / f"{tid}-escalation-{e['id']}.md").read_text(encoding="utf-8")
    assert "answer: a" in ef and "resolved: true" in ef
    world["planner"].patch(f"/nodes/{tid}", json={"state": "done"})
    assert {n["id"]: n for n in json.loads((proj_dir / "tree.json").read_text())}[tid]["state"] == "done"
    world["planner"].patch(f"/nodes/{tid}", json={"state": "open"})


def test_backup_concurrent_writes_serialized(world):
    """10 threads create docs on one node at once; every doc must be on disk afterwards and tree.json intact."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    base = _backup_dir()
    pid, tid = world["project"]["id"], world["task"]["id"]
    proj_dir = base / world["pa"]["uuid"]
    tok = world["worker_tok"]["token"]

    def post(i):
        with client(tok) as c:
            r = c.post(f"/nodes/{tid}/docs", json={"role": "report", "body": f"concurrent {i}"})
            assert r.status_code == 201, r.text
            return r.json()["id"]

    with ThreadPoolExecutor(max_workers=10) as ex:
        ids = list(ex.map(post, range(10)))
    for i, did in zip(range(10), ids):
        f = proj_dir / "docs" / f"{tid}-report-{did}.md"
        assert f.exists(), did
        assert f.read_text(encoding="utf-8").endswith(f"\n\nconcurrent {i}")
    tree = {n["id"]: n for n in json.loads((proj_dir / "tree.json").read_text())}
    assert tid in tree and tree[tid]["parent_id"] == pid


def _dsn():
    dsn = os.environ.get("PLANNER_DSN")
    if not dsn:
        pytest.skip("PLANNER_DSN not set (scripts/test_all.py sets it)")
    return dsn


def test_admin_secrets_are_never_stored(admin):
    """token_secrets holds planner and worker plaintexts only. Admin sessions live in memory; the
    admin password is only ever a salted hash in meta."""
    import psycopg
    dsn = _dsn()
    _, token = admin_login()  # a fresh admin session, so one certainly exists right now
    assert token.startswith("adm_")
    with psycopg.connect(dsn, autocommit=True) as conn:
        secrets = [r[0] for r in conn.execute("SELECT plaintext FROM token_secrets").fetchall()]
        assert secrets, "mint should have stored planner and worker plaintexts"
        assert all(s.startswith("pln_") for s in secrets)
        assert not any(s.startswith("adm_") for s in secrets)
        assert token not in secrets
        meta = [str(r[0]) for r in conn.execute("SELECT value FROM meta").fetchall()]
        assert not any(ADMIN_PASSWORD in v for v in meta)
        # and no column anywhere in the tokens or secrets tables holds the password or a session token
        for table in ("tokens", "token_secrets"):
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            flat = " ".join(str(x) for r in rows for x in r)
            assert ADMIN_PASSWORD not in flat and token not in flat


def test_bootstrap_twice_is_noop():
    import subprocess
    import psycopg
    from pathlib import Path
    dsn = _dsn()
    repo = Path(__file__).resolve().parent.parent
    r = subprocess.run(["uv", "run", "ai-project-planning-server", "bootstrap"], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "Already bootstrapped" in r.stdout and "adm_" not in r.stdout
    assert _db.read_access_token() == ACCESS[_db.ACCESS_HEADER]  # a second run does not rotate the access token
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM nodes WHERE parent_id IS NULL").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM meta WHERE key='root_node_id'").fetchone()[0] == 1


def test_backup_per_kb_and_not_for_fixed_roots(world):
    base = _backup_dir()
    kb_dir = base / "kb" / world["kb_prod"]["uuid"]
    assert (kb_dir / "tree.json").exists() and (kb_dir / "title").read_text(encoding="utf-8") == "Product\n"
    page = world["admin"].post("/nodes", json={"parent_id": world["kb_prod"]["node_id"], "title": "Glossary 2", "summary": "terms"}).json()
    assert any(p.name.startswith(f"{page['id']}-summary-") for p in (kb_dir / "docs").iterdir())
    assert (base / "kb" / world["kb_co"]["uuid"] / "tree.json").exists()
    assert not any(p.name.startswith("1-") or p.name.startswith("3-") for p in base.iterdir())


def test_spike_same_rule_as_report(world):
    w, p, tid = world["worker"], world["planner"], world["task"]["id"]
    assert w.post(f"/nodes/{tid}/docs", json={"role": "spike", "body": "hello world proof: screenshot at ..."}).status_code == 201
    assert p.post(f"/nodes/{world['project']['id']}/docs", json={"role": "spike", "body": "arch spike"}).status_code == 201
    assert w.post(f"/nodes/{world['project']['id']}/docs", json={"role": "spike", "body": "x"}).status_code == 404


def _chain(client, parent, n):
    out = []
    for i in range(n):
        r = client.post("/nodes", json={"parent_id": parent, "title": f"lvl{i}", "summary": "s"})
        out.append(r)
        if r.status_code != 201:
            break
        parent = r.json()["id"]
    return out


def test_depth_level4_flags_level5_refused(world):
    rs = _chain(world["admin"], world["plans"], 5)
    assert [r.status_code for r in rs[:4]] == [201] * 4
    assert rs[0].json()["uuid"] is not None and rs[1].json()["uuid"] is None  # a project gets a uuid, its children do not
    assert [r.json()["needs_review"] for r in rs[:4]] == [False, False, False, True]
    assert "warning" in rs[3].json() and "warning" not in rs[2].json()
    assert rs[4].status_code == 409
    assert "separate project under plans" in rs[4].json()["detail"]


def test_depth_kb_exempt(world):
    rs = _chain(world["admin"], world["kb_prod"]["node_id"], 6)
    assert all(r.status_code == 201 for r in rs)
    assert not any(r.json()["needs_review"] for r in rs)


def test_depth_level5_refused_direct_sql():
    import psycopg
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        plans = int(conn.execute("SELECT value FROM meta WHERE key='plans_node_id'").fetchone()[0])
        parent = plans
        for _ in range(4):
            parent = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'sql') RETURNING id", (parent,)).fetchone()[0]
        assert conn.execute("SELECT needs_review FROM nodes WHERE id=%s", (parent,)).fetchone()[0] is True
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'sql5')", (parent,))


def test_unknown_node_404(world):
    assert world["admin"].get("/nodes/999999").status_code == 404


def test_new_project_backed_up_immediately(world):
    """A project with only its summary must be on disk right after creation."""
    base = _backup_dir()
    p = world["admin"].post("/projects", json={"title": "Bare Project", "summary": "only a summary"}).json()
    d = base / p["uuid"]
    assert (d / "tree.json").exists() and (d / "title").read_text(encoding="utf-8") == "Bare Project\n"
    files = list((d / "docs").iterdir())
    assert len(files) == 1 and files[0].name.startswith(f"{p['node_id']}-summary-")
    assert files[0].read_text(encoding="utf-8").endswith("\n\nonly a summary")


def test_doc_history(world):
    w, p, tid = world["worker"], world["planner"], world["task"]["id"]
    r = w.post(f"/nodes/{tid}/docs", json={"role": "report", "body": "v1"}).json()
    assert w.get(f"/docs/{r['id']}/history").json() == []
    assert w.patch(f"/docs/{r['id']}", json={"body": "v2"}).status_code == 200
    assert w.patch(f"/docs/{r['id']}", json={"body": "v3"}).status_code == 200
    hist = p.get(f"/docs/{r['id']}/history").json()
    assert [h["body"] for h in hist] == ["v1", "v2"]
    assert all(h["doc_id"] == r["id"] for h in hist)
    assert [h["body"] for h in w.get(f"/docs/{r['id']}/history").json()] == ["v1", "v2"]
    # another worker in project B cannot see the doc at all
    other_tok = world["planner_b"].post("/tokens", json={"label": "w2", "scope_node_id": world["other"]["id"], "role": "worker"}).json()
    assert client(other_tok["token"]).get(f"/docs/{r['id']}/history").status_code == 404
    # a worker is not the author of the planner's instruction: 403 on its history even though it can read the doc
    assert w.get(f"/docs/{world['instr']['id']}/history").status_code == 403
    # history is in the backup
    base = _backup_dir()
    h = (base / world["pa"]["uuid"] / "docs" / f"{tid}-report-{r['id']}.history.md").read_text(encoding="utf-8")
    assert "v1" in h and "v2" in h and "v3" not in h and "edited_at:" in h


def test_kb_proposal_resolve_and_list(world):
    w, p, a, tid = world["worker"], world["planner"], world["admin"], world["task"]["id"]
    assert w.get("/proposals").status_code == 403
    prop = w.post(f"/nodes/{tid}/docs", json={"role": "kb_proposal", "body": "Add glossary term X"}).json()
    assert any(x["id"] == prop["id"] for x in p.get("/proposals").json())
    assert any(x["id"] == prop["id"] for x in a.get("/proposals").json())
    assert w.patch(f"/docs/{prop['id']}", json={"answer": "self", "resolved": True}).status_code == 403
    assert p.patch(f"/docs/{prop['id']}", json={"answer": "planner", "resolved": True}).status_code == 403
    r = a.patch(f"/docs/{prop['id']}", json={"answer": "approved by user, applied to kb", "resolved": True})
    assert r.status_code == 200 and r.json()["resolved"] is True
    assert all(x["id"] != prop["id"] for x in a.get("/proposals").json())
    rep = w.post(f"/nodes/{tid}/docs", json={"role": "report", "body": "r"}).json()
    assert a.patch(f"/docs/{rep['id']}", json={"resolved": True}).status_code == 422


def test_needs_review_clear_and_list(world):
    a, p = world["admin"], world["planner"]
    rs = _chain(p, world["project"]["id"], 3)  # levels 2, 3, 4 inside project A
    flagged = rs[2].json()
    assert flagged["needs_review"] is True
    assert flagged["id"] in {n["id"] for n in p.get("/nodes/review").json()}
    assert flagged["id"] in {n["id"] for n in a.get("/nodes/review").json()}
    tree = p.get(f"/nodes/{rs[0].json()['id']}/tree").json()
    assert "needs_review" in tree and tree["needs_review"] is False
    assert world["worker"].patch(f"/nodes/{flagged['id']}", json={"needs_review": False}).status_code in (403, 404)
    assert world["planner_b"].patch(f"/nodes/{flagged['id']}", json={"needs_review": False}).status_code == 403
    assert p.patch(f"/nodes/{flagged['id']}", json={}).status_code == 422
    r = p.patch(f"/nodes/{flagged['id']}", json={"needs_review": False})
    assert r.status_code == 200 and r.json()["needs_review"] is False
    assert flagged["id"] not in {n["id"] for n in p.get("/nodes/review").json()}
    assert world["worker"].get("/nodes/review").status_code == 200
