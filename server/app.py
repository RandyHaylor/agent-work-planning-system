from typing import Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from server import db
from server import permissions as P

app = FastAPI(title="Agent Planning Server", version="0.1.0")

ROLES = ("summary", "instruction", "report", "spike", "escalation", "question", "kb_proposal")
STATES = ("open", "blocked", "done")


class Ctx:
    def __init__(self, conn, principal: P.Principal, kb_root: int):
        self.conn, self.p, self.kb, self.anc = conn, principal, kb_root, db.ancestors_fn(conn)


def ctx(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM tokens WHERE token_hash = %s AND NOT revoked", (db.hash_token(authorization[7:]),)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(401, "bad token")
        root_tok = int(db.meta_get(conn, "root_token_id"))
        kb = int(db.meta_get(conn, "kb_node_id"))
        p = P.Principal(token_id=row["id"], scope_node_id=row["scope_node_id"], can_spawn=row["can_spawn"], is_root=row["id"] == root_tok)
        yield Ctx(conn, p, kb)
    finally:
        conn.close()


def get_node(c: Ctx, node_id: int):
    n = c.conn.execute("SELECT * FROM nodes WHERE id = %s", (node_id,)).fetchone()
    if not n or not P.can_read(c.p, node_id, c.anc, c.kb):
        raise HTTPException(404, "node not found")
    return n


def node_out(n):
    return {"id": n["id"], "parent_id": n["parent_id"], "title": n["title"], "owner": n["owner"], "state": n["state"], "needs_review": n["needs_review"], "created_at": n["created_at"]}


def doc_out(d):
    return {k: d[k] for k in ("id", "node_id", "role", "body", "author", "answer", "resolved", "created_at", "updated_at")}


@app.get("/me")
def me(c: Ctx = Depends(ctx)):
    t = c.conn.execute("SELECT label FROM tokens WHERE id = %s", (c.p.token_id,)).fetchone()
    return {"token_id": c.p.token_id, "label": t["label"], "scope_node_id": c.p.scope_node_id, "can_spawn": c.p.can_spawn, "is_root": c.p.is_root}


@app.get("/nodes/{node_id}")
def read_node(node_id: int, c: Ctx = Depends(ctx)):
    n = get_node(c, node_id)
    docs = c.conn.execute("SELECT * FROM docs WHERE node_id = %s ORDER BY id", (node_id,)).fetchall()
    children = c.conn.execute("SELECT id, title, state FROM nodes WHERE parent_id = %s ORDER BY id", (node_id,)).fetchall()
    return {**node_out(n), "docs": [doc_out(d) for d in docs], "children": children}


@app.get("/nodes/{node_id}/tree")
def read_tree(node_id: int, c: Ctx = Depends(ctx)):
    n = get_node(c, node_id)
    rows = c.conn.execute(
        """
        WITH RECURSIVE sub AS (
            SELECT id, parent_id, title, state FROM nodes WHERE id = %s
            UNION ALL
            SELECT n.id, n.parent_id, n.title, n.state FROM nodes n JOIN sub s ON n.parent_id = s.id
        ) SELECT * FROM sub ORDER BY id
        """,
        (node_id,),
    ).fetchall()
    by_id = {r["id"]: {"id": r["id"], "title": r["title"], "state": r["state"], "children": []} for r in rows}
    for r in rows:
        if r["id"] != node_id:
            by_id[r["parent_id"]]["children"].append(by_id[r["id"]])
    return by_id[node_id]


class NodeIn(BaseModel):
    parent_id: int
    title: str
    summary: str


@app.post("/nodes", status_code=201)
def create_node(body: NodeIn, c: Ctx = Depends(ctx)):
    get_node(c, body.parent_id)
    if not P.can_create_child(c.p, body.parent_id, c.anc, c.kb):
        raise HTTPException(403, "cannot create here")
    try:
        n = c.conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, %s, %s) RETURNING *", (body.parent_id, body.title, c.p.token_id)).fetchone()
    except psycopg.errors.CheckViolation as e:
        raise HTTPException(409, e.diag.message_primary)
    c.conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', %s, %s)", (n["id"], body.summary, c.p.token_id))
    out = node_out(n)
    if n["needs_review"]:
        out["warning"] = "level 4 node: needs_review is set. Review this branch with the user."
    return out


class StateIn(BaseModel):
    state: str


@app.patch("/nodes/{node_id}")
def set_state(node_id: int, body: StateIn, c: Ctx = Depends(ctx)):
    if body.state not in STATES:
        raise HTTPException(422, f"state must be one of {STATES}")
    n = get_node(c, node_id)
    parent_owner = None
    if n["parent_id"]:
        parent_owner = c.conn.execute("SELECT owner FROM nodes WHERE id = %s", (n["parent_id"],)).fetchone()["owner"]
    if not P.can_set_state(c.p, node_id, n["owner"], parent_owner, c.anc, c.kb):
        raise HTTPException(403, "cannot set state")
    n = c.conn.execute("UPDATE nodes SET state = %s WHERE id = %s RETURNING *", (body.state, node_id)).fetchone()
    return node_out(n)


class DocIn(BaseModel):
    role: str
    body: str


@app.post("/nodes/{node_id}/docs", status_code=201)
def create_doc(node_id: int, body: DocIn, c: Ctx = Depends(ctx)):
    if body.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    n = get_node(c, node_id)
    if not P.can_write_doc(c.p, node_id, n["owner"], body.role, c.anc, c.kb):
        raise HTTPException(403, "cannot write this doc role here")
    if body.role == "summary":
        raise HTTPException(409, "summary exists; edit it via PATCH /docs/{id}")
    d = c.conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, %s, %s, %s) RETURNING *", (node_id, body.role, body.body, c.p.token_id)).fetchone()
    return doc_out(d)


class DocPatch(BaseModel):
    body: Optional[str] = None
    answer: Optional[str] = None
    resolved: Optional[bool] = None


@app.patch("/docs/{doc_id}")
def patch_doc(doc_id: int, body: DocPatch, c: Ctx = Depends(ctx)):
    d = c.conn.execute("SELECT * FROM docs WHERE id = %s", (doc_id,)).fetchone()
    if not d or not P.can_read(c.p, d["node_id"], c.anc, c.kb):
        raise HTTPException(404, "doc not found")
    n = c.conn.execute("SELECT * FROM nodes WHERE id = %s", (d["node_id"],)).fetchone()
    if body.answer is not None or body.resolved is not None:
        if d["role"] != "escalation":
            raise HTTPException(422, "answer/resolved apply to escalations only")
        if not P.can_answer_escalation(c.p, d["node_id"], n["owner"], c.anc):
            raise HTTPException(403, "only the node owner answers escalations")
        c.conn.execute("UPDATE docs SET answer = COALESCE(%s, answer), resolved = COALESCE(%s, resolved), updated_at = now() WHERE id = %s", (body.answer, body.resolved, doc_id))
    if body.body is not None:
        if not P.can_edit_doc(c.p, d["node_id"], d["role"], d["author"], c.anc, c.kb):
            raise HTTPException(403, "cannot edit this doc")
        c.conn.execute("UPDATE docs SET body = %s, updated_at = now() WHERE id = %s", (body.body, doc_id))
    return doc_out(c.conn.execute("SELECT * FROM docs WHERE id = %s", (doc_id,)).fetchone())


@app.get("/escalations")
def escalations(c: Ctx = Depends(ctx)):
    rows = c.conn.execute(
        """
        WITH RECURSIVE sub AS (
            SELECT id FROM nodes WHERE id = %s
            UNION ALL SELECT n.id FROM nodes n JOIN sub s ON n.parent_id = s.id
        ) SELECT d.* FROM docs d JOIN sub ON d.node_id = sub.id
        WHERE d.role = 'escalation' AND NOT d.resolved ORDER BY d.id
        """,
        (c.p.scope_node_id,),
    ).fetchall()
    return [doc_out(d) for d in rows]


class TokenIn(BaseModel):
    label: str
    scope_node_id: int
    can_spawn: bool = False


@app.post("/tokens", status_code=201)
def mint(body: TokenIn, c: Ctx = Depends(ctx)):
    get_node(c, body.scope_node_id)
    if not P.can_mint(c.p, body.scope_node_id, body.can_spawn, c.anc):
        raise HTTPException(403, "cannot mint for that scope")
    raw = db.new_token()
    t = c.conn.execute(
        "INSERT INTO tokens (label, token_hash, scope_node_id, parent_token_id, can_spawn) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (body.label, db.hash_token(raw), body.scope_node_id, c.p.token_id, body.can_spawn),
    ).fetchone()
    return {"token_id": t["id"], "token": raw, "scope_node_id": body.scope_node_id, "can_spawn": body.can_spawn}


@app.delete("/tokens/{token_id}", status_code=204)
def revoke(token_id: int, c: Ctx = Depends(ctx)):
    t = c.conn.execute("SELECT parent_token_id FROM tokens WHERE id = %s", (token_id,)).fetchone()
    if not t:
        raise HTTPException(404, "token not found")
    if not P.can_revoke(c.p, t["parent_token_id"]):
        raise HTTPException(403, "only the minting token can revoke")
    c.conn.execute("UPDATE tokens SET revoked = true WHERE id = %s", (token_id,))
    return None
