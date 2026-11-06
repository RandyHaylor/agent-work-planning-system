"""Real integration tests over HTTPS against the running server and Postgres.

Requires: docker compose up, bootstrap done, server running, and the env var
PLANNER_ROOT_TOKEN set to the token bootstrap printed.
"""
import os

import httpx
import pytest

BASE = os.environ.get("PLANNER_URL", "https://localhost:8787")
ROOT = os.environ.get("PLANNER_ROOT_TOKEN")
if not ROOT:
    pytest.skip("PLANNER_ROOT_TOKEN not set", allow_module_level=True)


def client(token):
    return httpx.Client(base_url=BASE, verify=False, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(scope="module")
def root():
    return client(ROOT)


@pytest.fixture(scope="module")
def world(root):
    """root -> plans -> project(created by root) -> task ; sibling other-project.

    planner: role planner scoped to plans (did NOT create the project node).
    worker:  role worker scoped to task.
    """
    me = root.get("/me").json()
    tree = root.get(f"/nodes/{me['scope_node_id']}/tree").json()
    kids = {c["title"]: c["id"] for c in tree["children"]}
    plans, kb = kids["plans"], kids["kb"]
    project = root.post("/nodes", json={"parent_id": plans, "title": "project A", "summary": "Project A"}).json()
    other = root.post("/nodes", json={"parent_id": plans, "title": "project B", "summary": "Project B"}).json()
    planner_tok = root.post("/tokens", json={"label": "planner", "scope_node_id": plans, "role": "planner"}).json()
    planner = client(planner_tok["token"])
    env = planner.post(f"/nodes/{project['id']}/docs", json={"role": "environment", "body": "Stack: Python 3.12, stdlib only."}).json()
    task = planner.post("/nodes", json={"parent_id": project["id"], "title": "task 1", "summary": "Build module X"}).json()
    instr = planner.post(f"/nodes/{task['id']}/docs", json={"role": "instruction", "body": "Interfaces: ... DoD: ..."}).json()
    worker_tok = planner.post("/tokens", json={"label": "worker", "scope_node_id": task["id"], "role": "worker"}).json()
    worker = client(worker_tok["token"])
    return dict(root=root, planner=planner, worker=worker, plans=plans, kb=kb, project=project, other=other, task=task,
                instr=instr, env=env, planner_tok=planner_tok, worker_tok=worker_tok, root_node=me["scope_node_id"])


def test_401_without_token():
    assert httpx.get(f"{BASE}/me", verify=False).status_code == 401
    assert client("pln_bogus").get("/me").status_code == 401


def test_me_reports_role(world):
    w = world["worker"].get("/me").json()
    assert w["scope_node_id"] == world["task"]["id"] and w["role"] == "worker" and w["is_root"] is False
    p = world["planner"].get("/me").json()
    assert p["role"] == "planner" and p["is_root"] is False
    assert world["root"].get("/me").json()["role"] == "planner"


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


def test_worker_reads_kb(world):
    assert world["worker"].get(f"/nodes/{world['kb']}").status_code == 200


def test_worker_sees_ancestor_environment_doc(world):
    n = world["worker"].get(f"/nodes/{world['task']['id']}").json()
    assert [e["id"] for e in n["environment"]] == [world["env"]["id"]]
    assert n["environment"][0]["body"].startswith("Stack:")
    # the environment doc is NOT among the node's own docs
    assert all(d["role"] != "environment" for d in n["docs"])


def test_planner_reads_everything(world):
    """Planners are the admins: a planner scoped to project A still reads project B and the whole tree."""
    p = world["planner"]
    assert p.get(f"/nodes/{world['root_node']}").status_code == 200
    sub = client(p.post("/tokens", json={"label": "sub-planner", "scope_node_id": world["project"]["id"], "role": "planner"}).json()["token"])
    assert sub.get(f"/nodes/{world['other']['id']}").status_code == 200
    assert sub.get(f"/nodes/{world['other']['id']}/tree").status_code == 200
    titles = {c["title"] for c in sub.get(f"/nodes/{world['plans']}/tree").json()["children"]}
    assert {"project A", "project B"} <= titles
    # but it writes only inside its own scope
    assert sub.post(f"/nodes/{world['other']['id']}/docs", json={"role": "question", "body": "x"}).status_code == 403


def test_tree(world):
    t = world["planner"].get(f"/nodes/{world['project']['id']}/tree").json()
    assert t["children"][0]["id"] == world["task"]["id"]
    assert "docs" not in t


def test_planner_writes_question_on_node_it_did_not_create(world):
    """The case that failed in both live tests: root created the project; the planner must still log there."""
    pid = world["project"]["id"]
    r = world["planner"].post(f"/nodes/{pid}/docs", json={"role": "question", "body": "From node / Question / Answer / Answered by / Scope"})
    assert r.status_code == 201
    assert world["planner"].post(f"/nodes/{pid}/docs", json={"role": "instruction", "body": "plan of record"}).status_code == 201
    assert world["planner"].patch(f"/nodes/{pid}", json={"state": "blocked"}).status_code == 200
    assert world["planner"].patch(f"/nodes/{pid}", json={"state": "open"}).status_code == 200


def test_planner_edits_any_doc_in_scope(world):
    assert world["planner"].patch(f"/docs/{world['instr']['id']}", json={"body": "revised by planner"}).status_code == 200
    summary = [d for d in world["planner"].get(f"/nodes/{world['project']['id']}").json()["docs"] if d["role"] == "summary"][0]
    assert world["planner"].patch(f"/docs/{summary['id']}", json={"body": "edited summary (root-authored)"}).status_code == 200


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
    # it authored the sub-node's summary, so it may edit that; the planner's instruction on its own node stays locked
    summary = [d for d in w.get(f"/nodes/{cid}").json()["docs"] if d["role"] == "summary"][0]
    assert w.patch(f"/docs/{summary['id']}", json={"body": "sub summary, revised"}).status_code == 200
    assert w.patch(f"/docs/{world['instr']['id']}", json={"body": "nope"}).status_code == 403


def test_worker_cannot_create_outside_scope(world):
    # ancestors are invisible to a worker, so the parent is simply not found
    assert world["worker"].post("/nodes", json={"parent_id": world["project"]["id"], "title": "x", "summary": "x"}).status_code == 404
    # a planner scoped to the sibling project cannot create under plans itself
    sib = world["planner"].post("/tokens", json={"label": "sib", "scope_node_id": world["other"]["id"], "role": "planner"}).json()
    assert client(sib["token"]).post("/nodes", json={"parent_id": world["plans"], "title": "x", "summary": "x"}).status_code == 403


def test_state_planner_only(world):
    tid = world["task"]["id"]
    assert world["worker"].patch(f"/nodes/{tid}", json={"state": "blocked"}).status_code == 403
    assert world["planner"].patch(f"/nodes/{tid}", json={"state": "blocked"}).status_code == 200
    assert world["planner"].patch(f"/nodes/{tid}", json={"state": "bogus"}).status_code == 422


def test_escalation_flow(world):
    w, p, tid = world["worker"], world["planner"], world["task"]["id"]
    e = w.post(f"/nodes/{tid}/docs", json={"role": "escalation", "body": "Interface Y is ambiguous"}).json()
    assert any(x["id"] == e["id"] for x in p.get("/escalations").json())
    assert w.patch(f"/docs/{e['id']}", json={"answer": "self-answer"}).status_code == 403
    r = p.patch(f"/docs/{e['id']}", json={"answer": "Use Z", "resolved": True})
    assert r.status_code == 200 and r.json()["answer"] == "Use Z"
    assert all(x["id"] != e["id"] for x in p.get("/escalations").json())


def test_kb_planner_writable_worker_read_only(world):
    kb = world["kb"]
    page = world["planner"].post("/nodes", json={"parent_id": kb, "title": "Product", "summary": "What the product is"})
    assert page.status_code == 201
    assert world["planner"].post(f"/nodes/{kb}/docs", json={"role": "instruction", "body": "x"}).status_code == 201
    assert world["root"].post("/nodes", json={"parent_id": kb, "title": "Glossary", "summary": "terms"}).status_code == 201
    assert world["worker"].get(f"/nodes/{page.json()['id']}").status_code == 200
    assert world["worker"].post(f"/nodes/{kb}/docs", json={"role": "report", "body": "x"}).status_code == 403
    assert world["worker"].post("/nodes", json={"parent_id": kb, "title": "w", "summary": "s"}).status_code == 403
    assert world["worker"].post(f"/nodes/{world['task']['id']}/docs", json={"role": "kb_proposal", "body": "Add: ..."}).status_code == 201


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
    w, p = world["worker"], world["planner"]
    assert w.post("/tokens", json={"label": "x", "scope_node_id": world["task"]["id"], "role": "worker"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["kb"], "role": "worker"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["root_node"], "role": "worker"}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["task"]["id"], "role": "admin"}).status_code == 422
    sub = p.post("/tokens", json={"label": "sub", "scope_node_id": world["project"]["id"], "role": "planner"})
    assert sub.status_code == 201 and sub.json()["role"] == "planner"
    assert client(sub.json()["token"]).post("/tokens", json={"label": "x", "scope_node_id": world["other"]["id"], "role": "worker"}).status_code == 403


def test_revoke_rules(world):
    p, w = world["planner"], world["worker"]
    t = p.post("/tokens", json={"label": "tmp", "scope_node_id": world["task"]["id"], "role": "worker"}).json()
    assert w.delete(f"/tokens/{t['token_id']}").status_code == 403
    # a planner scoped to the sibling project can see this token but not revoke it
    sib = p.post("/tokens", json={"label": "sib2", "scope_node_id": world["other"]["id"], "role": "planner"}).json()
    assert client(sib["token"]).delete(f"/tokens/{t['token_id']}").status_code == 403
    # root did not mint it, but its scope contains the token's scope: allowed
    assert world["root"].delete(f"/tokens/{t['token_id']}").status_code == 204
    assert client(t["token"]).get("/me").status_code == 401
    assert p.delete(f"/tokens/{world['planner_tok']['token_id']}").status_code == 409


def test_revoke_cascades_through_minting_chain(world):
    p = world["planner"]
    sub = p.post("/tokens", json={"label": "sub-pl", "scope_node_id": world["project"]["id"], "role": "planner"}).json()
    grand = client(sub["token"]).post("/tokens", json={"label": "grand-w", "scope_node_id": world["task"]["id"], "role": "worker"}).json()
    assert client(grand["token"]).get("/me").status_code == 200
    assert p.delete(f"/tokens/{sub['token_id']}").status_code == 204
    assert client(sub["token"]).get("/me").status_code == 401
    assert client(grand["token"]).get("/me").status_code == 401
    listed = {t["id"]: t for t in p.get("/tokens").json()}
    assert listed[sub["token_id"]]["revoked"] is True and listed[sub["token_id"]]["active"] is False
    assert listed[grand["token_id"]]["revoked"] is False  # own flag untouched
    assert listed[grand["token_id"]]["active"] is False   # but dead through the chain
    assert listed[world["worker_tok"]["token_id"]]["active"] is True


def test_list_tokens(world):
    p, w = world["planner"], world["worker"]
    assert w.get("/tokens").status_code == 403
    rows = p.get("/tokens").json()
    ids = {t["id"] for t in rows}
    assert world["planner_tok"]["token_id"] in ids and world["worker_tok"]["token_id"] in ids
    assert all(set(t) >= {"id", "label", "role", "scope_node_id", "revoked"} for t in rows)
    sub = p.post("/tokens", json={"label": "scoped", "scope_node_id": world["project"]["id"], "role": "planner"}).json()
    sub_ids = {t["id"] for t in client(sub["token"]).get("/tokens").json()}
    assert world["worker_tok"]["token_id"] in sub_ids and world["planner_tok"]["token_id"] not in sub_ids


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
    proj_dir = next(p for p in base.iterdir() if p.name.startswith(f"{pid}-"))
    assert proj_dir.name == f"{pid}-project-a"
    tree = {n["id"]: n for n in json.loads((proj_dir / "tree.json").read_text())}
    assert pid in tree and tid in tree and tree[tid]["parent_id"] == pid
    r = world["worker"].post(f"/nodes/{tid}/docs", json={"role": "report", "body": "first draft "}).json()
    f = proj_dir / "docs" / f"{tid}-report-{r['id']}.md"
    assert f.exists()
    assert f.read_text(encoding="utf-8").endswith("\n\nfirst draft ")
    assert "author: worker" in f.read_text(encoding="utf-8")
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
    proj_dir = next(p for p in base.iterdir() if p.name.startswith(f"{pid}-"))
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


def test_bootstrap_twice_is_noop():
    import subprocess
    import psycopg
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    r = subprocess.run(["uv", "run", "python", "-m", "server", "bootstrap"], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "Already bootstrapped" in r.stdout and "ROOT_TOKEN" not in r.stdout
    with psycopg.connect(os.environ["PLANNER_DSN"], autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM nodes WHERE parent_id IS NULL").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM meta WHERE key='root_node_id'").fetchone()[0] == 1


def test_backup_kb_and_not_for_fixed_roots(world):
    base = _backup_dir()
    page = world["root"].post("/nodes", json={"parent_id": world["kb"], "title": "Glossary", "summary": "terms"}).json()
    assert (base / "kb" / "tree.json").exists()
    assert any(p.name.startswith(f"{page['id']}-summary-") for p in (base / "kb" / "docs").iterdir())
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
    rs = _chain(world["root"], world["plans"], 5)
    assert [r.status_code for r in rs[:4]] == [201] * 4
    assert [r.json()["needs_review"] for r in rs[:4]] == [False, False, False, True]
    assert "warning" in rs[3].json() and "warning" not in rs[2].json()
    assert rs[4].status_code == 409
    assert "separate project under plans" in rs[4].json()["detail"]


def test_depth_kb_exempt(world):
    rs = _chain(world["root"], world["kb"], 6)
    assert all(r.status_code == 201 for r in rs)
    assert not any(r.json()["needs_review"] for r in rs)


def test_depth_level5_refused_direct_sql():
    import psycopg
    with psycopg.connect(os.environ["PLANNER_DSN"], autocommit=True) as conn:
        plans = int(conn.execute("SELECT value FROM meta WHERE key='plans_node_id'").fetchone()[0])
        parent = plans
        for _ in range(4):
            parent = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'sql') RETURNING id", (parent,)).fetchone()[0]
        assert conn.execute("SELECT needs_review FROM nodes WHERE id=%s", (parent,)).fetchone()[0] is True
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'sql5')", (parent,))


def test_unknown_node_404(world):
    assert world["root"].get("/nodes/999999").status_code == 404
