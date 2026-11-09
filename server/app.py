import os
import uuid as _uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import urllib.parse

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from server import admin as A
from server import backup as B
from server import db
from server import permissions as P

app = FastAPI(title="Agent Planning Server", version="0.3.0")
SESSIONS = A.SessionStore()  # admin sessions: this process only; a restart clears them
TEST_HOOKS = os.environ.get("PLANNER_TEST_HOOKS") == "1"

ROLES = tuple(sorted(P.ALL_DOC_ROLES))
STATES = ("open", "blocked", "done")
BACKUP_DIR = Path(os.environ.get("PLANNER_BACKUP_DIR", Path(__file__).resolve().parent.parent / "backups"))


class Ctx:
    def __init__(self, conn, principal: P.Principal, view: P.View):
        self.conn, self.p, self.v, self.anc = conn, principal, view, db.ancestors_fn(conn)
        self.kb, self.plans, self.root = view.kb, view.plans, view.root

    def backup_root(self, node_id: int) -> Optional[int]:
        return B.backup_root_for(self.anc(node_id), self.plans, self.kb)

    @contextmanager
    def write(self, node_id: int):
        """One transaction around a write touching node_id, then a synchronous backup of
        that node's project (or kb) subtree. Writes to one project are serialized with a
        transaction-scoped advisory lock, so backups never interleave: a concurrent write
        waits its turn. Any failure, including backup, rolls back.

        Yields a holder dict; a caller that creates a new project or kb sets holder["root"]
        to the new node after the insert, since nothing exists to derive it from beforehand."""
        with self.conn.transaction():
            holder = {"root": self.backup_root(node_id)}
            if holder["root"] is not None:
                self.conn.execute("SELECT pg_advisory_xact_lock(%s)", (holder["root"],))
            yield holder
            if holder["root"] is not None:
                try:
                    B.backup_subtree(self.conn, holder["root"], BACKUP_DIR, self.kb)
                except B.BackupError as e:
                    raise HTTPException(500, f"backup failed, write rolled back: {e}")

    def can_read(self, node_id: int) -> bool:
        return P.can_read(self.p, node_id, self.anc, self.v)


def _build_view(conn, role: str, scope: int, root: int, kb: int, plans: int, anc) -> tuple[Optional[int], P.View]:
    """The project the scope lies in, and what this principal may read beyond it."""
    project = P.project_of(scope, anc, plans)
    projects, kbs = set(), set()
    if role != P.ADMIN and project is not None:
        kbs = {r["kb_node_id"] for r in conn.execute("SELECT kb_node_id FROM project_kbs WHERE project_node_id = %s", (project,)).fetchall()}
        if role == P.PLANNER:
            projects = {r["id"] for r in conn.execute("SELECT id FROM nodes WHERE parent_id = %s AND visible", (plans,)).fetchall()}
            projects |= {r["target_project_id"] for r in conn.execute("SELECT target_project_id FROM project_visibility WHERE viewer_project_id = %s", (project,)).fetchall()}
            projects.add(project)
    return project, P.View(root=root, plans=plans, kb=kb, readable_projects=frozenset(projects), readable_kbs=frozenset(kbs))


def _meta_ids(conn) -> tuple[int, int, int]:
    meta = {k: db.meta_get(conn, k) for k in ("root_node_id", "kb_node_id", "plans_node_id", "admin_pw_hash")}
    if any(v is None for v in meta.values()):
        raise HTTPException(503, "database not bootstrapped: run `uv run python -m server bootstrap`")
    return tuple(int(meta[k]) for k in ("root_node_id", "kb_node_id", "plans_node_id"))


def ctx(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    bearer = authorization[7:]
    conn = db.connect()
    try:
        root, kb, plans = _meta_ids(conn)
        anc = db.ancestors_fn(conn)
        if A.is_session_token(bearer):
            # The admin: an in-memory session approved by the user, never a database row.
            if not SESSIONS.touch(bearer):
                raise HTTPException(401, "admin session unknown, expired, or lost at server restart: run admin-login again")
            p = P.Principal(token_id=None, scope_node_id=root, role=P.ADMIN, project_id=None)
            yield Ctx(conn, p, P.View(root=root, plans=plans, kb=kb))
            return
        # A token is revoked if it, or any token in its minting chain, is revoked.
        h = db.hash_token(bearer)
        row = conn.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT t.*, t.revoked AS any_revoked FROM tokens t WHERE token_hash = %s
                UNION ALL
                SELECT p.*, (c.any_revoked OR p.revoked) FROM tokens p JOIN chain c ON p.id = c.parent_token_id
            ) SELECT (SELECT bool_or(any_revoked) FROM chain) AS dead, * FROM chain
            WHERE token_hash = %s
            """,
            (h, h),
        ).fetchone()
        if not row or row["dead"]:
            raise HTTPException(401, "bad token")
        project, view = _build_view(conn, row["role"], row["scope_node_id"], root, kb, plans, anc)
        p = P.Principal(token_id=row["id"], scope_node_id=row["scope_node_id"], role=row["role"], project_id=project)
        yield Ctx(conn, p, view)
    finally:
        conn.close()


# ---------- admin login: the user approves an agent as admin by typing the password into the browser ----------

@app.post("/admin/nonce", status_code=201)
def admin_nonce():
    """Unauthenticated: start a login. The CLI opens /admin/login?nonce=... for the user."""
    return {"nonce": SESSIONS.new_nonce()}


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(nonce: str = ""):
    if not SESSIONS.nonce_valid(nonce):
        raise HTTPException(404, "unknown or expired login nonce; run admin-login again")
    return HTMLResponse(A.login_page(nonce))


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    form = urllib.parse.parse_qs((await request.body()).decode("utf-8"))
    nonce = (form.get("nonce") or [""])[0]
    password = (form.get("password") or [""])[0]
    if not SESSIONS.nonce_valid(nonce):
        raise HTTPException(404, "unknown or expired login nonce; run admin-login again")
    if SESSIONS.rate_limited():
        raise HTTPException(429, "too many failed logins; wait a minute")
    with db.connect() as conn:
        _meta_ids(conn)
        salt, h = db.meta_get(conn, "admin_pw_salt"), db.meta_get(conn, "admin_pw_hash")
    if not A.verify_password(password, salt, h):
        SESSIONS.record_failure()
        return HTMLResponse(A.login_page(nonce, "Wrong password."), status_code=401)
    SESSIONS.login(nonce)
    return HTMLResponse(A.DONE_PAGE)


@app.get("/admin/session/{nonce}")
def admin_session(nonce: str):
    """Returns the session token exactly once after the user approved; 404 before and after."""
    token = SESSIONS.pickup(nonce)
    if token is None:
        raise HTTPException(404, "no approved session for this nonce")
    return {"token": token}


@app.post("/admin/logout", status_code=204)
def admin_logout(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer ") or not A.is_session_token(authorization[7:]):
        raise HTTPException(401, "admin session token required")
    if not SESSIONS.logout(authorization[7:]):
        raise HTTPException(401, "no such session")
    return None


if TEST_HOOKS:
    @app.post("/admin/_clear_sessions", status_code=204)
    def admin_clear_sessions():
        """Test hook (PLANNER_TEST_HOOKS=1 only): what a server restart does to admin sessions."""
        SESSIONS.clear()
        return None


def get_node(c: Ctx, node_id: int):
    n = c.conn.execute("SELECT * FROM nodes WHERE id = %s", (node_id,)).fetchone()
    if not n or not c.can_read(node_id):
        raise HTTPException(404, "node not found")
    return n


def node_by_uuid(c: Ctx, u: str, parent: Optional[int] = None):
    try:
        _uuid.UUID(u)
    except ValueError:
        raise HTTPException(404, "not found")
    n = c.conn.execute("SELECT * FROM nodes WHERE uuid = %s", (u,)).fetchone()
    if not n or (parent is not None and n["parent_id"] != parent) or not c.can_read(n["id"]):
        raise HTTPException(404, "not found")
    return n


def node_out(n):
    out = {k: n[k] for k in ("id", "parent_id", "title", "owner", "state", "needs_review", "visible", "created_at")}
    out["uuid"] = str(n["uuid"]) if n["uuid"] else None
    return out


def doc_out(d):
    return {k: d[k] for k in ("id", "node_id", "role", "body", "author", "answer", "resolved", "created_at", "updated_at")}


@app.get("/me")
def me(c: Ctx = Depends(ctx)):
    if c.p.role == P.ADMIN:
        return {"token_id": None, "label": "admin", "scope_node_id": c.p.scope_node_id, "role": P.ADMIN,
                "project_node_id": None, "project_uuid": None}
    t = c.conn.execute("SELECT label FROM tokens WHERE id = %s", (c.p.token_id,)).fetchone()
    proj = None
    if c.p.project_id is not None:
        pr = c.conn.execute("SELECT uuid FROM nodes WHERE id = %s", (c.p.project_id,)).fetchone()
        proj = str(pr["uuid"]) if pr and pr["uuid"] else None
    return {"token_id": c.p.token_id, "label": t["label"], "scope_node_id": c.p.scope_node_id, "role": c.p.role,
            "project_node_id": c.p.project_id, "project_uuid": proj}


# ---------- projects and knowledge bases (admin) ----------

def project_out(n, c: Ctx):
    kbs = c.conn.execute("SELECT n.uuid FROM project_kbs pk JOIN nodes n ON n.id = pk.kb_node_id WHERE pk.project_node_id = %s ORDER BY n.id", (n["id"],)).fetchall()
    return {"uuid": str(n["uuid"]), "node_id": n["id"], "title": n["title"], "state": n["state"], "visible": n["visible"],
            "kbs": [str(k["uuid"]) for k in kbs]}


class ProjectIn(BaseModel):
    title: str
    summary: str


@app.post("/projects", status_code=201)
def create_project(body: ProjectIn, c: Ctx = Depends(ctx)):
    """Admin only: a new project under plans with a uuid, and its planner token (returned once)."""
    if not P.can_manage_projects(c.p):
        raise HTTPException(403, "admin only")
    raw = db.new_token()
    with c.write(c.plans) as holder:
        n = c.conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, %s, %s) RETURNING *", (c.plans, body.title, c.p.token_id)).fetchone()
        c.conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', %s, %s)", (n["id"], body.summary, c.p.token_id))
        t = c.conn.execute(
            "INSERT INTO tokens (label, token_hash, scope_node_id, parent_token_id, role) VALUES (%s, %s, %s, %s, 'planner') RETURNING id",
            (f"planner:{body.title}", db.hash_token(raw), n["id"], c.p.token_id),
        ).fetchone()
        holder["root"] = n["id"]
    return {**project_out(n, c), "planner_token": raw, "planner_token_id": t["id"]}


@app.get("/projects")
def list_projects(c: Ctx = Depends(ctx)):
    rows = c.conn.execute("SELECT * FROM nodes WHERE parent_id = %s ORDER BY id", (c.plans,)).fetchall()
    return [project_out(n, c) for n in rows if c.can_read(n["id"])]


class ProjectPatch(BaseModel):
    visible: Optional[bool] = None
    kbs: Optional[list[str]] = None


@app.patch("/projects/{project_uuid}")
def patch_project(project_uuid: str, body: ProjectPatch, c: Ctx = Depends(ctx)):
    """Admin only: set visibility and/or replace the set of kbs the project may read."""
    if not P.can_manage_projects(c.p):
        raise HTTPException(403, "admin only")
    if body.visible is None and body.kbs is None:
        raise HTTPException(422, "nothing to change: give visible or kbs")
    n = node_by_uuid(c, project_uuid, parent=c.plans)
    kb_ids = []
    for u in body.kbs or []:
        kb_ids.append(node_by_uuid(c, u, parent=c.kb)["id"])
    with c.write(n["id"]):
        if body.visible is not None:
            n = c.conn.execute("UPDATE nodes SET visible = %s WHERE id = %s RETURNING *", (body.visible, n["id"])).fetchone()
        if body.kbs is not None:
            c.conn.execute("DELETE FROM project_kbs WHERE project_node_id = %s", (n["id"],))
            for k in kb_ids:
                c.conn.execute("INSERT INTO project_kbs (project_node_id, kb_node_id) VALUES (%s, %s)", (n["id"], k))
    return project_out(n, c)


class VisibilityIn(BaseModel):
    viewer: str


@app.post("/projects/{project_uuid}/visibility", status_code=201)
def grant_visibility(project_uuid: str, body: VisibilityIn, c: Ctx = Depends(ctx)):
    """Admin only: let the viewer project read this (possibly hidden) project."""
    if not P.can_manage_projects(c.p):
        raise HTTPException(403, "admin only")
    target = node_by_uuid(c, project_uuid, parent=c.plans)
    viewer = node_by_uuid(c, body.viewer, parent=c.plans)
    c.conn.execute("INSERT INTO project_visibility (viewer_project_id, target_project_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (viewer["id"], target["id"]))
    return {"target": project_uuid, "viewer": body.viewer}


@app.delete("/projects/{project_uuid}/visibility/{viewer_uuid}", status_code=204)
def revoke_visibility(project_uuid: str, viewer_uuid: str, c: Ctx = Depends(ctx)):
    if not P.can_manage_projects(c.p):
        raise HTTPException(403, "admin only")
    target = node_by_uuid(c, project_uuid, parent=c.plans)
    viewer = node_by_uuid(c, viewer_uuid, parent=c.plans)
    c.conn.execute("DELETE FROM project_visibility WHERE viewer_project_id = %s AND target_project_id = %s", (viewer["id"], target["id"]))
    return None


class KbIn(BaseModel):
    title: str
    summary: str


@app.post("/kbs", status_code=201)
def create_kb(body: KbIn, c: Ctx = Depends(ctx)):
    """Admin only: a new knowledge base under kb with a uuid."""
    if not P.can_manage_projects(c.p):
        raise HTTPException(403, "admin only")
    with c.write(c.kb) as holder:
        n = c.conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, %s, %s) RETURNING *", (c.kb, body.title, c.p.token_id)).fetchone()
        c.conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', %s, %s)", (n["id"], body.summary, c.p.token_id))
        holder["root"] = n["id"]
    return {"uuid": str(n["uuid"]), "node_id": n["id"], "title": n["title"]}


@app.get("/kbs")
def list_kbs(c: Ctx = Depends(ctx)):
    rows = c.conn.execute("SELECT * FROM nodes WHERE parent_id = %s ORDER BY id", (c.kb,)).fetchall()
    return [{"uuid": str(n["uuid"]), "node_id": n["id"], "title": n["title"]} for n in rows if c.can_read(n["id"])]


# ---------- nodes ----------

@app.get("/nodes/review")
def nodes_needing_review(c: Ctx = Depends(ctx)):
    """Nodes with needs_review set, limited to what the caller can read."""
    rows = c.conn.execute("SELECT * FROM nodes WHERE needs_review ORDER BY id").fetchall()
    return [node_out(n) for n in rows if c.can_read(n["id"])]


@app.get("/nodes/{node_id}")
def read_node(node_id: int, c: Ctx = Depends(ctx)):
    n = get_node(c, node_id)
    docs = c.conn.execute("SELECT * FROM docs WHERE node_id = %s ORDER BY id", (node_id,)).fetchall()
    children = c.conn.execute("SELECT id, title, state FROM nodes WHERE parent_id = %s ORDER BY id", (node_id,)).fetchall()
    if node_id in (c.root, c.plans, c.kb):
        children = [ch for ch in children if c.can_read(ch["id"])]
    # Environment docs from every ancestor of this node (not the node itself). Visible to all roles.
    chain = c.anc(node_id)[1:]
    env = []
    if chain:
        env = c.conn.execute("SELECT * FROM docs WHERE role = %s AND node_id = ANY(%s) ORDER BY id", (P.ENV_ROLE, chain)).fetchall()
    return {**node_out(n), "docs": [doc_out(d) for d in docs], "environment": [doc_out(d) for d in env], "children": children}


@app.get("/nodes/{node_id}/tree")
def read_tree(node_id: int, c: Ctx = Depends(ctx)):
    get_node(c, node_id)
    rows = c.conn.execute(
        """
        WITH RECURSIVE sub AS (
            SELECT id, parent_id, title, state, needs_review FROM nodes WHERE id = %s
            UNION ALL
            SELECT n.id, n.parent_id, n.title, n.state, n.needs_review FROM nodes n JOIN sub s ON n.parent_id = s.id
        ) SELECT * FROM sub ORDER BY id
        """,
        (node_id,),
    ).fetchall()
    if node_id in (c.root, c.plans, c.kb):
        # above the project level, hide what the caller may not read (hidden projects, unassigned kbs)
        rows = [r for r in rows if c.can_read(r["id"])]
    by_id = {r["id"]: {"id": r["id"], "title": r["title"], "state": r["state"], "needs_review": r["needs_review"], "children": []} for r in rows}
    for r in rows:
        if r["id"] != node_id and r["parent_id"] in by_id:
            by_id[r["parent_id"]]["children"].append(by_id[r["id"]])
    return by_id[node_id]


class NodeIn(BaseModel):
    parent_id: int
    title: str
    summary: str


@app.post("/nodes", status_code=201)
def create_node(body: NodeIn, c: Ctx = Depends(ctx)):
    get_node(c, body.parent_id)
    if not P.can_create_child(c.p, body.parent_id, c.anc, c.v):
        raise HTTPException(403, "cannot create here")
    try:
        with c.write(body.parent_id) as holder:
            n = c.conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, %s, %s) RETURNING *", (body.parent_id, body.title, c.p.token_id)).fetchone()
            c.conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', %s, %s)", (n["id"], body.summary, c.p.token_id))
            if holder["root"] is None:
                # A new project or kb: its backup root is itself, known only after the insert.
                holder["root"] = c.backup_root(n["id"])
    except psycopg.errors.CheckViolation as e:
        raise HTTPException(409, e.diag.message_primary)
    out = node_out(n)
    if n["needs_review"]:
        out["warning"] = "level 4 node: needs_review is set. Review this branch with the user."
    return out


class NodePatch(BaseModel):
    state: Optional[str] = None
    needs_review: Optional[bool] = None


@app.patch("/nodes/{node_id}")
def patch_node(node_id: int, body: NodePatch, c: Ctx = Depends(ctx)):
    """Set state, or clear needs_review after the user has reviewed a level-4 branch."""
    if body.state is None and body.needs_review is None:
        raise HTTPException(422, "nothing to change: give state or needs_review")
    if body.state is not None and body.state not in STATES:
        raise HTTPException(422, f"state must be one of {STATES}")
    get_node(c, node_id)
    if not P.can_set_state(c.p, node_id, c.anc, c.v):
        raise HTTPException(403, "cannot change this node")
    with c.write(node_id):
        n = c.conn.execute(
            "UPDATE nodes SET state = COALESCE(%s, state), needs_review = COALESCE(%s, needs_review) WHERE id = %s RETURNING *",
            (body.state, body.needs_review, node_id),
        ).fetchone()
    return node_out(n)


# ---------- docs ----------

class DocIn(BaseModel):
    role: str
    body: str


@app.post("/nodes/{node_id}/docs", status_code=201)
def create_doc(node_id: int, body: DocIn, c: Ctx = Depends(ctx)):
    if body.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    get_node(c, node_id)
    if not P.can_write_doc(c.p, node_id, body.role, c.anc, c.v):
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
    if not d or not c.can_read(d["node_id"]):
        raise HTTPException(404, "doc not found")
    if body.answer is not None or body.resolved is not None:
        if d["role"] == "escalation":
            if not P.can_answer_escalation(c.p, d["node_id"], c.anc, c.v):
                raise HTTPException(403, "only the project's planner or the admin answers escalations")
        elif d["role"] == "kb_proposal":
            if not P.can_resolve_proposal(c.p):
                raise HTTPException(403, "only the admin resolves kb proposals")
        else:
            raise HTTPException(422, "answer/resolved apply to escalation and kb_proposal only")
    if body.body is not None and not P.can_edit_doc(c.p, d["node_id"], d["role"], d["author"], c.anc, c.v):
        raise HTTPException(403, "cannot edit this doc")
    with c.write(d["node_id"]):
        if body.answer is not None or body.resolved is not None:
            c.conn.execute("UPDATE docs SET answer = COALESCE(%s, answer), resolved = COALESCE(%s, resolved), updated_at = now() WHERE id = %s", (body.answer, body.resolved, doc_id))
        if body.body is not None:
            c.conn.execute("UPDATE docs SET body = %s, updated_at = now() WHERE id = %s", (body.body, doc_id))
    return doc_out(c.conn.execute("SELECT * FROM docs WHERE id = %s", (doc_id,)).fetchone())


def version_out(v):
    return {k: v[k] for k in ("id", "doc_id", "body", "author", "answer", "resolved", "edited_at")}


@app.get("/docs/{doc_id}/history")
def doc_history(doc_id: int, c: Ctx = Depends(ctx)):
    """Previous versions of a doc, oldest first. Admin, planners that can read it, or the author."""
    d = c.conn.execute("SELECT * FROM docs WHERE id = %s", (doc_id,)).fetchone()
    if not d or not c.can_read(d["node_id"]):
        raise HTTPException(404, "doc not found")
    if c.p.role == P.WORKER and d["author"] != c.p.token_id:
        raise HTTPException(403, "history is visible to planners and the doc's author")
    rows = c.conn.execute("SELECT * FROM doc_versions WHERE doc_id = %s ORDER BY id", (doc_id,)).fetchall()
    return [version_out(v) for v in rows]


def _unresolved_in_scope(c: Ctx, role: str):
    return c.conn.execute(
        """
        WITH RECURSIVE sub AS (
            SELECT id FROM nodes WHERE id = %s
            UNION ALL SELECT n.id FROM nodes n JOIN sub s ON n.parent_id = s.id
        ) SELECT d.* FROM docs d JOIN sub ON d.node_id = sub.id
        WHERE d.role = %s AND NOT d.resolved ORDER BY d.id
        """,
        (c.p.scope_node_id, role),
    ).fetchall()


@app.get("/escalations")
def escalations(c: Ctx = Depends(ctx)):
    return [doc_out(d) for d in _unresolved_in_scope(c, "escalation")]


@app.get("/proposals")
def proposals(c: Ctx = Depends(ctx)):
    """Unresolved kb_proposal docs in the caller's scope. Admin sees all; a planner its project's."""
    if c.p.role == P.WORKER:
        raise HTTPException(403, "admin or planner only")
    return [doc_out(d) for d in _unresolved_in_scope(c, "kb_proposal")]


# ---------- tokens ----------

class TokenIn(BaseModel):
    label: str
    scope_node_id: int
    role: str = "worker"


@app.post("/tokens", status_code=201)
def mint(body: TokenIn, c: Ctx = Depends(ctx)):
    if body.role not in P.TOKEN_ROLES:
        raise HTTPException(422, f"role must be one of {sorted(P.TOKEN_ROLES)}; the admin is a login session, not a token")
    get_node(c, body.scope_node_id)
    if not P.can_mint(c.p, body.scope_node_id, body.role, c.anc, c.v):
        raise HTTPException(403, "cannot mint that role for that scope")
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
    """Tokens whose scope lies within the caller's scope. Admin and planners.
    `revoked` is the token's own flag; `active` is its effective liveness through the chain."""
    if not P.can_list_tokens(c.p):
        raise HTTPException(403, "admin or planner only")
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
    if not t or not c.can_read(t["scope_node_id"]):
        raise HTTPException(404, "token not found")
    if c.p.token_id is not None and token_id == c.p.token_id:
        raise HTTPException(409, "a token cannot revoke itself")
    if not P.can_revoke(c.p, t["scope_node_id"], c.anc, c.v):
        raise HTTPException(403, "only the admin, or the planner of the token's project, can revoke")
    c.conn.execute("UPDATE tokens SET revoked = true WHERE id = %s", (token_id,))
    return None
