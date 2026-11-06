import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from server import backup as B
from server import db
from server import permissions as P

app = FastAPI(title="Agent Planning Server", version="0.1.0")

ROLES = ("summary", "instruction", "environment", "report", "spike", "escalation", "question", "kb_proposal", "survey", "approval", "review")
STATES = ("open", "blocked", "done")
BACKUP_DIR = Path(os.environ.get("PLANNER_BACKUP_DIR", Path(__file__).resolve().parent.parent / "backups"))


class Ctx:
    def __init__(self, conn, principal: P.Principal, kb_root: int, plans_root: int):
        self.conn, self.p, self.kb, self.plans, self.anc = conn, principal, kb_root, plans_root, db.ancestors_fn(conn)

    @contextmanager
    def write(self, node_id: int):
        """One transaction around a write touching node_id, then a synchronous backup of
        that node's project (or kb) subtree. Writes to one project are serialized with a
        transaction-scoped advisory lock, so backups never interleave: a concurrent write
        waits its turn. Any failure, including backup, rolls back."""
        with self.conn.transaction():
            root = B.backup_root_for(self.anc(node_id), self.plans, self.kb)
            if root is not None:
                self.conn.execute("SELECT pg_advisory_xact_lock(%s)", (root,))
            yield
            if root is not None:
                try:
                    B.backup_subtree(self.conn, root, BACKUP_DIR, self.kb)
                except B.BackupError as e:
                    raise HTTPException(500, f"backup failed, write rolled back: {e}")


def ctx(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    conn = db.connect()
    try:
        # A token is revoked if it, or any token in its minting chain, is revoked.
        row = conn.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT t.*, t.revoked AS any_revoked FROM tokens t WHERE token_hash = %s
                UNION ALL
                SELECT p.*, (c.any_revoked OR p.revoked) FROM tokens p JOIN chain c ON p.id = c.parent_token_id
            ) SELECT (SELECT bool_or(any_revoked) FROM chain) AS dead, * FROM chain
            WHERE token_hash = %s
            """,
            (db.hash_token(authorization[7:]), db.hash_token(authorization[7:])),
        ).fetchone()
        if not row or row["dead"]:
            raise HTTPException(401, "bad token")
        root_tok = int(db.meta_get(conn, "root_token_id"))
        kb = int(db.meta_get(conn, "kb_node_id"))
        plans = int(db.meta_get(conn, "plans_node_id"))
        p = P.Principal(token_id=row["id"], scope_node_id=row["scope_node_id"], role=row["role"], is_root=row["id"] == root_tok)
        yield Ctx(conn, p, kb, plans)
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
    return {"token_id": c.p.token_id, "label": t["label"], "scope_node_id": c.p.scope_node_id, "role": c.p.role, "is_root": c.p.is_root}


@app.get("/nodes/{node_id}")
def read_node(node_id: int, c: Ctx = Depends(ctx)):
    n = get_node(c, node_id)
    docs = c.conn.execute("SELECT * FROM docs WHERE node_id = %s ORDER BY id", (node_id,)).fetchall()
    children = c.conn.execute("SELECT id, title, state FROM nodes WHERE parent_id = %s ORDER BY id", (node_id,)).fetchall()
    # Environment docs from every ancestor of this node (not the node itself). Visible to all roles.
    chain = c.anc(node_id)[1:]
    env = []
    if chain:
        env = c.conn.execute("SELECT * FROM docs WHERE role = %s AND node_id = ANY(%s) ORDER BY id", (P.ENV_ROLE, chain)).fetchall()
    return {**node_out(n), "docs": [doc_out(d) for d in docs], "environment": [doc_out(d) for d in env], "children": children}


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
        with c.write(body.parent_id):
            n = c.conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, %s, %s) RETURNING *", (body.parent_id, body.title, c.p.token_id)).fetchone()
            c.conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', %s, %s)", (n["id"], body.summary, c.p.token_id))
    except psycopg.errors.CheckViolation as e:
        raise HTTPException(409, e.diag.message_primary)
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
    get_node(c, node_id)
    if not P.can_set_state(c.p, node_id, c.anc, c.kb):
        raise HTTPException(403, "cannot set state")
    with c.write(node_id):
        n = c.conn.execute("UPDATE nodes SET state = %s WHERE id = %s RETURNING *", (body.state, node_id)).fetchone()
    return node_out(n)


class DocIn(BaseModel):
    role: str
    body: str


@app.post("/nodes/{node_id}/docs", status_code=201)
def create_doc(node_id: int, body: DocIn, c: Ctx = Depends(ctx)):
    if body.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    get_node(c, node_id)
    if not P.can_write_doc(c.p, node_id, body.role, c.anc, c.kb):
        raise HTTPException(403, "cannot write this doc role here")
    if body.role == "summary":
        raise HTTPException(409, "summary exists; edit it via PATCH /docs/{id}")
    with c.write(node_id):
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
    if body.answer is not None or body.resolved is not None:
        if d["role"] != "escalation":
            raise HTTPException(422, "answer/resolved apply to escalations only")
        if not P.can_answer_escalation(c.p, d["node_id"], c.anc):
            raise HTTPException(403, "only a planner answers escalations")
    if body.body is not None and not P.can_edit_doc(c.p, d["node_id"], d["role"], d["author"], c.anc, c.kb):
        raise HTTPException(403, "cannot edit this doc")
    with c.write(d["node_id"]):
        if body.answer is not None or body.resolved is not None:
            c.conn.execute("UPDATE docs SET answer = COALESCE(%s, answer), resolved = COALESCE(%s, resolved), updated_at = now() WHERE id = %s", (body.answer, body.resolved, doc_id))
        if body.body is not None:
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
    role: str = "worker"


@app.post("/tokens", status_code=201)
def mint(body: TokenIn, c: Ctx = Depends(ctx)):
    if body.role not in P.ROLES:
        raise HTTPException(422, f"role must be one of {sorted(P.ROLES)}")
    get_node(c, body.scope_node_id)
    if not P.can_mint(c.p, body.scope_node_id, body.role, c.anc):
        raise HTTPException(403, "cannot mint for that scope")
    raw = db.new_token()
    t = c.conn.execute(
        "INSERT INTO tokens (label, token_hash, scope_node_id, parent_token_id, role) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (body.label, db.hash_token(raw), body.scope_node_id, c.p.token_id, body.role),
    ).fetchone()
    return {"token_id": t["id"], "token": raw, "scope_node_id": body.scope_node_id, "role": body.role}


def token_out(t, active: bool):
    out = {k: t[k] for k in ("id", "label", "role", "scope_node_id", "parent_token_id", "revoked", "created_at")}
    out["active"] = active  # false if this token or any token in its minting chain is revoked
    return out


@app.get("/tokens")
def list_tokens(c: Ctx = Depends(ctx)):
    """Tokens whose scope lies within the caller's scope. Planner only.
    `revoked` is the token's own flag; `active` is its effective liveness through the chain."""
    if not P.can_list_tokens(c.p):
        raise HTTPException(403, "planner only")
    rows = c.conn.execute(
        """
        WITH RECURSIVE sub AS (
            SELECT id FROM nodes WHERE id = %s
            UNION ALL SELECT n.id FROM nodes n JOIN sub s ON n.parent_id = s.id
        ) SELECT t.* FROM tokens t JOIN sub ON t.scope_node_id = sub.id ORDER BY t.id
        """,
        (c.p.scope_node_id,),
    ).fetchall()
    chain = {r["id"]: (r["parent_token_id"], r["revoked"]) for r in c.conn.execute("SELECT id, parent_token_id, revoked FROM tokens").fetchall()}

    def active(tid):
        while tid is not None:
            parent, revoked = chain[tid]
            if revoked:
                return False
            tid = parent
        return True

    return [token_out(t, active(t["id"])) for t in rows]


@app.delete("/tokens/{token_id}", status_code=204)
def revoke(token_id: int, c: Ctx = Depends(ctx)):
    t = c.conn.execute("SELECT scope_node_id FROM tokens WHERE id = %s", (token_id,)).fetchone()
    if not t or not P.can_read(c.p, t["scope_node_id"], c.anc, c.kb):
        raise HTTPException(404, "token not found")
    if token_id == c.p.token_id:
        raise HTTPException(409, "a token cannot revoke itself")
    if not P.can_revoke(c.p, t["scope_node_id"], c.anc):
        raise HTTPException(403, "only a planner whose scope contains the token's scope can revoke")
    c.conn.execute("UPDATE tokens SET revoked = true WHERE id = %s", (token_id,))
    return None
