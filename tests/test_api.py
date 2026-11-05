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
    """root -> plans -> plan(planner-owned) -> task(planner-owned) ; sibling other-plan."""
    me = root.get("/me").json()
    tree = root.get(f"/nodes/{me['scope_node_id']}/tree").json()
    kids = {c["title"]: c["id"] for c in tree["children"]}
    plans, kb = kids["plans"], kids["kb"]
    plan = root.post("/nodes", json={"parent_id": plans, "title": "plan A", "summary": "Plan A"}).json()
    other = root.post("/nodes", json={"parent_id": plans, "title": "plan B", "summary": "Plan B"}).json()
    planner_tok = root.post("/tokens", json={"label": "planner", "scope_node_id": plan["id"], "can_spawn": True}).json()
    planner = client(planner_tok["token"])
    task = planner.post("/nodes", json={"parent_id": plan["id"], "title": "task 1", "summary": "Build module X"}).json()
    instr = planner.post(f"/nodes/{task['id']}/docs", json={"role": "instruction", "body": "Interfaces: ... DoD: ..."}).json()
    dev_tok = planner.post("/tokens", json={"label": "dev", "scope_node_id": task["id"], "can_spawn": False}).json()
    dev = client(dev_tok["token"])
    return dict(root=root, planner=planner, dev=dev, plans=plans, kb=kb, plan=plan, other=other, task=task,
                instr=instr, planner_tok=planner_tok, dev_tok=dev_tok, root_node=me["scope_node_id"])


def test_401_without_token():
    assert httpx.get(f"{BASE}/me", verify=False).status_code == 401
    assert client("pln_bogus").get("/me").status_code == 401


def test_me(world):
    me = world["dev"].get("/me").json()
    assert me["scope_node_id"] == world["task"]["id"]
    assert me["can_spawn"] is False and me["is_root"] is False


def test_node_has_summary_and_instruction(world):
    n = world["dev"].get(f"/nodes/{world['task']['id']}").json()
    roles = sorted(d["role"] for d in n["docs"])
    assert roles == ["instruction", "summary"]


def test_dev_reads_ancestors_and_kb_not_siblings(world):
    d = world["dev"]
    assert d.get(f"/nodes/{world['plan']['id']}").status_code == 200
    assert d.get(f"/nodes/{world['root_node']}").status_code == 200
    assert d.get(f"/nodes/{world['kb']}").status_code == 200
    assert d.get(f"/nodes/{world['other']['id']}").status_code == 404


def test_tree(world):
    t = world["planner"].get(f"/nodes/{world['plan']['id']}/tree").json()
    assert t["children"][0]["id"] == world["task"]["id"]
    assert "docs" not in t


def test_dev_cannot_write_instruction_or_summary_on_own_scope(world):
    d, tid = world["dev"], world["task"]["id"]
    assert d.post(f"/nodes/{tid}/docs", json={"role": "instruction", "body": "x"}).status_code == 403
    assert d.post(f"/nodes/{tid}/docs", json={"role": "summary", "body": "x"}).status_code == 403
    assert d.patch(f"/docs/{world['instr']['id']}", json={"body": "hacked"}).status_code == 403


def test_dev_writes_report_beneath_and_edits_own(world):
    d, tid = world["dev"], world["task"]["id"]
    r = d.post(f"/nodes/{tid}/docs", json={"role": "report", "body": "built it"})
    assert r.status_code == 201
    assert d.patch(f"/docs/{r.json()['id']}", json={"body": "built it, proven"}).status_code == 200
    assert world["planner"].patch(f"/docs/{r.json()['id']}", json={"body": "nope"}).status_code == 403


def test_dev_creates_child_node_and_owns_its_summary(world):
    d, tid = world["dev"], world["task"]["id"]
    child = d.post("/nodes", json={"parent_id": tid, "title": "sub", "summary": "sub summary"})
    assert child.status_code == 201
    cid = child.json()["id"]
    assert d.post(f"/nodes/{cid}/docs", json={"role": "instruction", "body": "sub instr"}).status_code == 201
    sid = [x for x in d.get(f"/nodes/{cid}").json()["docs"] if x["role"] == "summary"][0]["id"]
    assert d.patch(f"/docs/{sid}", json={"body": "edited"}).status_code == 200
    assert d.patch(f"/nodes/{cid}", json={"state": "done"}).status_code == 200


def test_dev_cannot_create_outside_scope(world):
    assert world["dev"].post("/nodes", json={"parent_id": world["plan"]["id"], "title": "x", "summary": "x"}).status_code == 403


def test_state_rules(world):
    tid = world["task"]["id"]
    assert world["dev"].patch(f"/nodes/{tid}", json={"state": "blocked"}).status_code == 403
    assert world["planner"].patch(f"/nodes/{tid}", json={"state": "blocked"}).status_code == 200
    assert world["planner"].patch(f"/nodes/{tid}", json={"state": "bogus"}).status_code == 422


def test_escalation_flow(world):
    d, p, tid = world["dev"], world["planner"], world["task"]["id"]
    e = d.post(f"/nodes/{tid}/docs", json={"role": "escalation", "body": "Interface Y is ambiguous"}).json()
    assert any(x["id"] == e["id"] for x in p.get("/escalations").json())
    assert d.patch(f"/docs/{e['id']}", json={"answer": "self-answer"}).status_code == 403
    r = p.patch(f"/docs/{e['id']}", json={"answer": "Use Z", "resolved": True})
    assert r.status_code == 200 and r.json()["answer"] == "Use Z"
    assert all(x["id"] != e["id"] for x in p.get("/escalations").json())


def test_question_log_owner_only(world):
    tid = world["task"]["id"]
    assert world["planner"].post(f"/nodes/{tid}/docs", json={"role": "question", "body": "dev asked ..."}).status_code == 201
    assert world["dev"].post(f"/nodes/{tid}/docs", json={"role": "question", "body": "x"}).status_code == 403


def test_kb_root_only(world):
    kb = world["kb"]
    assert world["planner"].post("/nodes", json={"parent_id": kb, "title": "p", "summary": "s"}).status_code == 403
    assert world["dev"].post(f"/nodes/{kb}/docs", json={"role": "report", "body": "x"}).status_code == 403
    page = world["root"].post("/nodes", json={"parent_id": kb, "title": "Product", "summary": "What the product is"})
    assert page.status_code == 201
    assert world["dev"].get(f"/nodes/{page.json()['id']}").status_code == 200
    # proposal is written in the dev's own scope, handed off by role
    assert world["dev"].post(f"/nodes/{world['task']['id']}/docs", json={"role": "kb_proposal", "body": "Add: ..."}).status_code == 201


def test_mint_rules(world):
    d, p = world["dev"], world["planner"]
    assert d.post("/tokens", json={"label": "x", "scope_node_id": world["task"]["id"]}).status_code == 403
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["other"]["id"]}).status_code == 404
    assert p.post("/tokens", json={"label": "x", "scope_node_id": world["plans"]}).status_code == 403


def test_revoke_rules(world):
    p, d = world["planner"], world["dev"]
    t = p.post("/tokens", json={"label": "tmp", "scope_node_id": world["task"]["id"]}).json()
    assert d.delete(f"/tokens/{t['token_id']}").status_code == 403
    assert world["root"].delete(f"/tokens/{t['token_id']}").status_code == 403
    assert p.delete(f"/tokens/{t['token_id']}").status_code == 204
    assert client(t["token"]).get("/me").status_code == 401


def test_spike_same_rule_as_report(world):
    d, p, tid = world["dev"], world["planner"], world["task"]["id"]
    assert d.post(f"/nodes/{tid}/docs", json={"role": "spike", "body": "three.js hello world: screenshot at ..."}).status_code == 201
    assert p.post(f"/nodes/{world['plan']['id']}/docs", json={"role": "spike", "body": "arch spike"}).status_code == 201
    assert d.post(f"/nodes/{world['plan']['id']}/docs", json={"role": "spike", "body": "x"}).status_code == 403


def _chain(client, parent, n):
    """Create n nested nodes under parent; return list of responses."""
    out = []
    for i in range(n):
        r = client.post("/nodes", json={"parent_id": parent, "title": f"lvl{i}", "summary": "s"})
        out.append(r)
        if r.status_code != 201:
            break
        parent = r.json()["id"]
    return out


def test_depth_level4_flags_level5_refused(world):
    root = world["root"]
    rs = _chain(root, world["plans"], 5)  # levels 1..5
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
    dsn = os.environ.get("PLANNER_DSN", "postgresql://planner:planner@localhost:5433/planner")
    with psycopg.connect(dsn, autocommit=True) as conn:
        plans = int(conn.execute("SELECT value FROM meta WHERE key='plans_node_id'").fetchone()[0])
        parent = plans
        for _ in range(4):
            parent = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'sql') RETURNING id", (parent,)).fetchone()[0]
        assert conn.execute("SELECT needs_review FROM nodes WHERE id=%s", (parent,)).fetchone()[0] is True
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO nodes (parent_id, title) VALUES (%s, 'sql5')", (parent,))


def test_unknown_node_404(world):
    assert world["root"].get("/nodes/999999").status_code == 404
