"""Fakes for api_client.

- FakePlanningServer: an in-memory server behind httpx.MockTransport implementing the BUILD-PLAN.md
  routes just enough for client tests. It records every request.
- FakePlanningApiClient: a minimal working PlanningApiClientInterface (stands in for the real client).
- RecordingPlanningApiClient: records each method call and returns a canned dict (no HTTP); for cli tests.
"""
from __future__ import annotations

import base64
import hashlib
import inspect
import itertools
import json as jsonlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Union
from urllib.parse import urlparse

import httpx

from planning_system.errors import Forbidden, Halted, Invalid, NotFound

from .interface import PlanningApiClientInterface
from .types import ApiError, ClientSettings

NODE_STATES = ("open", "assigned", "in_progress", "done", "abandoned")


# --------------------------------------------------------------------------- fake server

@dataclass
class RecordedRequest:
    method: str
    path: str
    params: dict
    body: Any
    headers: dict


@dataclass
class FakePlanningServer:
    admin_password: str = "correct horse"
    requests: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self._ids = itertools.count(1)
        self.tokens: dict[str, dict] = {}
        self.nodes: dict[int, dict] = {}
        self.content: dict[int, list] = {}
        self.references: dict[int, dict] = {}
        self.agents: dict[str, dict] = {}
        self.credentials: dict[int, dict] = {}
        self.reviews: dict[str, dict] = {}
        self.review_packets: dict[str, dict] = {}
        self.candidates: dict[str, dict] = {}
        self.halt_state: dict = {"system": False, "projects": []}
        self._fail_next: Optional[tuple[int, Any]] = None
        self._routes = self._build_routes()

    # ---- helpers for tests
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def issue_token(self, role: str = "admin", project_id: Optional[int] = None,
                    scope_node_id: Optional[int] = None, agent_id: Optional[str] = None) -> str:
        token = f"tok-{role}-{next(self._ids)}"
        self.tokens[token] = {"agent_id": agent_id, "role": role, "project_id": project_id,
                              "scope_node_id": scope_node_id}
        return token

    def fail_next(self, status: int, body: Any) -> None:
        self._fail_next = (status, body)

    def seed_project(self, title: str = "Project") -> dict:
        return self._new_node(None, title, "what we're doing", "summary", [], None)

    def seed_review(self, project_id: int, node_id: int, claim_text: str = "The user wants X [ref-1:1-1].",
                    claim_tag: str = "requirement", citations: Optional[list] = None,
                    node_title: str = "Node", node_context_summary: str = "summary") -> dict:
        """Opens a pending review record (what the server does on an accepted content write)."""
        review_id = f"rev-{next(self._ids)}"
        content_reference_id = f"ref-{next(self._ids)}"
        self.reviews[review_id] = {
            "id": review_id, "project_id": project_id, "node_id": node_id,
            "content_reference_id": content_reference_id, "claim_tag": claim_tag, "status": "pending",
            "reviewer": None, "taken_at": None, "reason": "", "suggested_title": None,
            "created_at": f"2026-11-25T00:00:{len(self.reviews):02d}+00:00", "decided_at": None}
        self.review_packets[review_id] = {
            "review_id": review_id, "node_title": node_title, "node_context_summary": node_context_summary,
            "claim_tag": claim_tag, "claim_text": claim_text,
            "citations": citations if citations is not None else [{
                "citation": "[ref-1:1-1]", "origin": "user_exchange", "quoted_text": "I want X.",
                "pre_text": "Agent: what do you want?", "full_text": "I want X."}]}
        return self.reviews[review_id]

    # ---- request handling
    def handle(self, request: httpx.Request) -> httpx.Response:
        body = jsonlib.loads(request.content) if request.content else None
        self.requests.append(RecordedRequest(request.method, request.url.path,
                                             dict(request.url.params), body, dict(request.headers)))
        if self._fail_next is not None:
            status, fail_body = self._fail_next
            self._fail_next = None
            return httpx.Response(status, json=fail_body)
        for method, pattern, needs_auth, handler in self._routes:
            match = re.fullmatch(pattern, request.url.path)
            if method == request.method and match:
                principal = self._principal(request)
                if needs_auth and principal is None:
                    return httpx.Response(403, json={"detail": "not authenticated"})
                if self._refused_while_halted(method, request.url.path, principal, body or {}):
                    return httpx.Response(423, json={"error": "Halted", "detail": "halted: writes are refused"})
                try:
                    result = handler(principal, body or {}, dict(request.url.params), *match.groups())
                except (KeyError, LookupError):
                    return httpx.Response(404, json={"detail": "not found"})
                except _Status as status:
                    return httpx.Response(status.code, json={"detail": status.detail})
                if result is NO_CONTENT:
                    return httpx.Response(204)
                return httpx.Response(200, json=result)
        return httpx.Response(404, json={"detail": "no such route"})

    def _refused_while_halted(self, method: str, path: str, principal: Optional[dict], body: dict) -> bool:
        """Server halt (build log #68), simplified: every non-GET except admin sessions and halt itself."""
        if method == "GET" or path in ("/admin/sessions", "/admin/halt", "/admin/unhalt"):
            return False
        if self.halt_state["system"]:
            return True
        project = (principal or {}).get("project_id") or body.get("project_id")
        return project is not None and int(project) in self.halt_state["projects"]

    def _halt(self, principal, body, query):
        if principal["role"] != "admin":
            raise _Status(403, "admin only")
        if body.get("project_id") is None:
            self.halt_state["system"] = True
        else:
            self.halt_state["projects"].append(int(body["project_id"]))
        return self._halt_view()

    def _unhalt(self, principal, body, query):
        if principal["role"] != "admin":
            raise _Status(403, "admin only")
        if body.get("project_id") is None:
            self.halt_state["system"] = False
        else:
            self.halt_state["projects"] = [p for p in self.halt_state["projects"] if p != int(body["project_id"])]
        return self._halt_view()

    def _halt_view(self) -> dict:
        return {"system": self.halt_state["system"], "projects": sorted(self.halt_state["projects"])}

    def _principal(self, request: httpx.Request) -> Optional[dict]:
        header = request.headers.get("authorization", "")
        return self.tokens.get(header.removeprefix("Bearer ").strip()) if header else None

    # ---- domain stand-ins
    def _new_node(self, parent_id, title, level_label, context_summary, labels, depends_on) -> dict:
        node_id = next(self._ids)
        node = {"id": node_id, "parent_id": parent_id, "title": title, "level_label": level_label,
                "context_summary": context_summary, "labels": list(labels or []),
                "depends_on": list(depends_on or []), "state": "open", "assignee": None, "branch": None}
        self.nodes[node_id] = node
        return node

    def _node(self, node_id) -> dict:
        return self.nodes[int(node_id)]

    def _build_routes(self) -> list:
        n = r"(\d+)"
        rid = r"([^/]+)"
        return [
            ("POST", "/admin/sessions", False, self._admin_session),
            ("DELETE", "/admin/sessions", True, lambda p, b, q: {"ended": True}),
            ("POST", "/admin/halt", True, self._halt),
            ("POST", "/admin/unhalt", True, self._unhalt),
            ("GET", "/admin/halt", True, lambda p, b, q: self._halt_view()),
            ("GET", "/me", True, lambda p, b, q: dict(p)),
            ("POST", "/credentials", True, self._mint),
            ("POST", "/credentials/quote-key", True, self._mint_quote_key),
            ("POST", f"/credentials/{n}/revoke", True, lambda p, b, q, i: {"id": int(i), "revoked": True}),
            ("POST", f"/credentials/{n}/rotate", True, lambda p, b, q, i: {"id": int(i), "token": f"rot-{i}"}),
            ("POST", "/agents", True, self._register_agent),
            ("POST", "/projects", True, lambda p, b, q: self._new_node(
                None, b["title"], "what we're doing", b["context_summary"], [], None)),
            ("POST", "/nodes", True, lambda p, b, q: self._new_node(
                self._node(b["parent_id"])["id"], b["title"], b["level_label"], b["context_summary"],
                b.get("labels"), b.get("depends_on"))),
            ("GET", "/nodes", True, lambda p, b, q: [x for x in self.nodes.values() if x["state"] == q.get("state")]),
            ("GET", f"/nodes/{n}", True, lambda p, b, q, i: self._node(i)),
            ("GET", f"/nodes/{n}/children", True, lambda p, b, q, i: self._children(i)),
            ("GET", f"/nodes/{n}/ancestors", True, lambda p, b, q, i: self._ancestors(i)),
            ("GET", f"/nodes/{n}/ready-children", True,
             lambda p, b, q, i: [c for c in self._children(i) if c["state"] == "open"]),
            ("PATCH", f"/nodes/{n}", True, lambda p, b, q, i: self._node(i).update(b) or self._node(i)),
            ("POST", f"/nodes/{n}/move", True, lambda p, b, q, i: self._node(i).update(
                parent_id=self._node(b["new_parent_id"])["id"]) or self._node(i)),
            ("POST", f"/nodes/{n}/state", True, self._set_state),
            ("POST", f"/nodes/{n}/assign", True, self._assign),
            ("POST", f"/nodes/{n}/supplementary", True, self._supplementary),
            ("POST", f"/nodes/{n}/content", True, self._add_content),
            ("PUT", f"/nodes/{n}/content/{n}", True,
             lambda p, b, q, i, r: {"node_id": int(i), "reference_id": int(r), "text": b["text"]}),
            ("GET", f"/nodes/{n}/context", True, lambda p, b, q, i: {
                "node": self._node(i), "context": f"context for {self._node(i)['title']}"}),
            ("POST", "/reader/load", True, self._reader_load),
            ("GET", f"/reader/{rid}/toc", True, lambda p, b, q, i: {"id": i, "toc": []}),
            ("GET", f"/reader/{rid}/get", True, lambda p, b, q, i: {"id": i, "params": q, "text": ""}),
            ("POST", "/reader/search", True, lambda p, b, q: {"terms": b["terms"], "hits": []}),
            ("POST", f"/reader/{rid}/json", True, lambda p, b, q, i: {"id": i, "flags": b["flags"]}),
            ("GET", f"/reader/{rid}/lines", True, lambda p, b, q, i: {"id": i, "lines": []}),
            ("POST", "/reader/cite", True, self._cite),
            ("GET", f"/references/{n}", True, lambda p, b, q, i: self.references[int(i)]),
            ("GET", f"/references/{n}/lines", True, lambda p, b, q, i: {"id": int(i), "lines": []}),
            ("POST", "/references/render", True, lambda p, b, q: {"citation": b["citation"], "text": ""}),
            ("POST", "/references/user-exchange", True, self._user_exchange),
            ("GET", f"/projects/{n}/open-items", True, self._open_items),
            ("GET", "/references/search", True, lambda p, b, q: [
                {"id": f"ref-{i}", "origin": "document", "locator": None, "preview": r.get("citation", "")}
                for i, r in self.references.items() if q["q"].lower() in str(r).lower()]),
            ("POST", "/supersede-candidates", True, self._propose_supersede),
            ("GET", "/supersede-candidates", True, lambda p, b, q: [
                c for c in self.candidates.values() if c["project_id"] == int(q["project_id"])
                and q.get("status") in (None, c["status"])]),
            ("POST", f"/supersede-candidates/{rid}/confirm", True,
             lambda p, b, q, i: {"candidate": self._decide(p, i, "confirmed", ""), "reopened_review_ids": []}),
            ("POST", f"/supersede-candidates/{rid}/reject", True,
             lambda p, b, q, i: self._decide(p, i, "rejected", b["reason"])),
            ("GET", "/reviews", True, self._list_reviews),
            ("POST", "/reviews/take", True, self._take_review),
            ("GET", f"/reviews/{rid}", True, lambda p, b, q, i: self.reviews[i]),
            ("POST", f"/reviews/{rid}/verdict", True, self._submit_verdict),
            ("POST", f"/reviews/{rid}/release", True, self._release_review),
            ("GET", "/guidance/templates", True, lambda p, b, q: ["Planner", "Worker"]),
            ("GET", "/guidance/rules", True, lambda p, b, q: []),
            ("GET", f"/guidance/{rid}", True, lambda p, b, q, role: {
                "role": role, "template": role.title(), "text": f"{role} guidance"}),
        ]

    def _admin_session(self, principal, body, query):
        if body.get("password") != self.admin_password:
            raise _Status(403, "wrong password")
        return {"token": self.issue_token("admin")}

    def _mint(self, principal, body, query):
        credential_id = next(self._ids)
        token = self.issue_token(body["role"], body.get("project_id"), body.get("scope_node_id"),
                                 body.get("agent_id"))
        self.credentials[credential_id] = {"token": token, **body}
        return {"credential_id": credential_id, "token": token}

    def _mint_quote_key(self, principal, body, query):
        return {"credential_id": next(self._ids), "token": self.issue_token("quote_client")}

    def _register_agent(self, principal, body, query):
        self.agents[body["agent_id"]] = body
        return body

    def _children(self, node_id):
        self._node(node_id)
        return [x for x in self.nodes.values() if x["parent_id"] == int(node_id)]

    def _ancestors(self, node_id):
        chain, node = [], self._node(node_id)
        while node["parent_id"] is not None:
            node = self._node(node["parent_id"])
            chain.append(node)
        return chain

    def _set_state(self, principal, body, query, node_id):
        if body.get("state") not in NODE_STATES:
            raise _Status(422, "unknown state")
        self._node(node_id)["state"] = body["state"]
        return self._node(node_id)

    def _assign(self, principal, body, query, node_id):
        node = self._node(node_id)
        node.update(state="assigned", assignee=body["agent_id"], branch=body["branch"])
        token = self.issue_token("worker", principal.get("project_id"), node["id"], body["agent_id"])
        return {"node": node, "worker_token": token}

    def _supplementary(self, principal, body, query, node_id):
        node = self._node(node_id)
        new = self._new_node(node["parent_id"], body["title"], body["kind"], body["context_summary"], [], None)
        node["depends_on"].append(new["id"])
        return new

    def _add_content(self, principal, body, query, node_id):
        item = {"node_id": self._node(node_id)["id"], "reference_id": next(self._ids),
                "text": body["text"], "tags": body.get("tags", [])}
        self.content.setdefault(int(node_id), []).append(item)
        return item

    def _reader_load(self, principal, body, query):
        source = body.get("url") or body.get("file_name") or body.get("search_terms")
        return [{"cache_id": f"c{next(self._ids)}", "toc": [], "strategy_used": body.get("strategy") or "auto",
                 "metadata": {"source": source}}]

    def _cite(self, principal, body, query):
        reference_id = next(self._ids)
        citation = f"[{body['id']}:{body['start_line']}-{body['end_line']}]"
        self.references[reference_id] = {"id": reference_id, "citation": citation}
        return {"reference_id": reference_id, "citation": citation}

    def _user_exchange(self, principal, body, query):
        if principal["role"] != "quote_client":
            raise _Status(403, "quote key only")
        digest = hashlib.sha256(f"{body['user_message']}\0{body['pre_text']}".encode()).hexdigest()
        for reference in self.references.values():
            if reference.get("hash") == digest:
                return {"reference_id": reference["id"]}
        reference_id = next(self._ids)
        self.references[reference_id] = {"id": reference_id, "hash": digest, **body}
        return {"reference_id": reference_id}


    def _open_items(self, principal, body, query, project_id):
        return [{"node_id": node_id, "node_title": self.nodes[node_id]["title"], "reference_id": item["reference_id"],
                 "lines": [line.strip() for line in item["text"].splitlines() if line.strip()]}
                for node_id, items in self.content.items() for item in items if "open_items" in item["tags"]]

    # ---- content reviews (05-spec-citation-enforcement-and-review.md; no permission checks in the fake)
    def _list_reviews(self, principal, body, query):
        return [r for r in self.reviews.values()
                if r["project_id"] == int(query["project_id"])
                and query.get("status") in (None, r["status"])
                and (query.get("node_id") is None or r["node_id"] == int(query["node_id"]))]

    def _take_review(self, principal, body, query):
        pending = sorted((r for r in self.reviews.values()
                          if r["project_id"] == int(body["project_id"]) and r["status"] == "pending"),
                         key=lambda r: r["created_at"])
        if not pending:
            return NO_CONTENT
        record = pending[0]
        record.update(status="taken", reviewer=principal.get("agent_id"), taken_at="2026-11-25T01:00:00+00:00")
        return self.review_packets[record["id"]]

    def _held(self, principal, review_id) -> dict:
        record = self.reviews[review_id]
        if record["status"] != "taken" or record["reviewer"] != principal.get("agent_id"):
            raise _Status(409, "not the holder of a taken review")
        return record

    def _submit_verdict(self, principal, body, query, review_id):
        record = self._held(principal, review_id)
        record.update(status="passed" if body["passed"] else "failed", reason=body["reason"],
                      suggested_title=body.get("suggested_title"), findings=list(body.get("findings") or []),
                      reviewed_with=body.get("reviewed_with"), decided_at="2026-11-25T02:00:00+00:00")
        return record

    # ---- supersede candidates (no permission checks in the fake)
    def _propose_supersede(self, principal, body, query):
        candidate_id = f"sup-{next(self._ids)}"
        self.candidates[candidate_id] = {
            "id": candidate_id, "project_id": body["project_id"], "old_reference_id": body["old_reference_id"],
            "new_reference_id": body["new_reference_id"], "kind": "document", "found_by": "proposed",
            "status": "proposed", "proposed_by": principal.get("agent_id"), "reason": body.get("reason", ""),
            "decided_by": None, "request_node_id": None}
        return self.candidates[candidate_id]

    def _decide(self, principal, candidate_id, status, reason):
        candidate = self.candidates[candidate_id]
        if candidate["status"] not in ("proposed", "trial_reviewed"):
            raise _Status(409, f"supersede candidate {candidate_id} is already {candidate['status']}")
        candidate.update(status=status, decided_by=principal.get("agent_id") or principal["role"],
                         reason=reason or candidate["reason"])
        return candidate

    def _release_review(self, principal, body, query, review_id):
        record = self._held(principal, review_id)
        record.update(status="pending", reviewer=None, taken_at=None)
        return record


NO_CONTENT = object()


class _Status(Exception):
    def __init__(self, code: int, detail: str):
        self.code, self.detail = code, detail


# --------------------------------------------------------------------------- fake client

class FakePlanningApiClient(PlanningApiClientInterface):
    """Minimal working client over any httpx transport (the fake server's MockTransport in tests)."""

    def __init__(self, settings: ClientSettings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._transport = transport

    def with_token(self, token):
        return FakePlanningApiClient(ClientSettings(self._settings.base_url, self._settings.ca_cert_path,
                                                    token, self._settings.timeout_seconds), self._transport)

    @property
    def tls_verify(self) -> Union[str, bool]:
        if self._settings.ca_cert_path is not None:
            return str(self._settings.ca_cert_path)
        return urlparse(self._settings.base_url).hostname not in ("127.0.0.1", "localhost", "::1")

    def _call(self, method: str, path: str, json: Any = None, params: Optional[dict] = None) -> Any:
        headers = {"Authorization": f"Bearer {self._settings.token}"} if self._settings.token else {}
        with httpx.Client(base_url=self._settings.base_url, transport=self._transport,
                          verify=self.tls_verify, timeout=self._settings.timeout_seconds) as client:
            clean_params = {k: v for k, v in (params or {}).items() if v is not None}
            response = client.request(method, path, json=json, params=clean_params, headers=headers)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.is_success:
            return body
        detail = body.get("detail", body) if isinstance(body, dict) else body
        error_type = {404: NotFound, 403: Forbidden, 422: Invalid, 423: Halted}.get(response.status_code)
        if error_type is not None:
            raise error_type(str(detail))
        raise ApiError(response.status_code, body)

    def start_admin_session(self, password):
        return self._call("POST", "/admin/sessions", {"password": password})

    def end_admin_session(self):
        return self._call("DELETE", "/admin/sessions")

    def me(self):
        return self._call("GET", "/me")

    def mint_credential(self, role, project_id, scope_node_id, agent_id):
        return self._call("POST", "/credentials", {"role": role, "project_id": project_id,
                                                   "scope_node_id": scope_node_id, "agent_id": agent_id})

    def mint_quote_key(self, install_label):
        return self._call("POST", "/credentials/quote-key", {"install_label": install_label})

    def revoke_credential(self, credential_id):
        return self._call("POST", f"/credentials/{credential_id}/revoke")

    def rotate_credential(self, credential_id):
        return self._call("POST", f"/credentials/{credential_id}/rotate")

    def register_agent(self, agent_id, **metadata):
        return self._call("POST", "/agents", {"agent_id": agent_id, **metadata})

    def create_project(self, title, context_summary):
        return self._call("POST", "/projects", {"title": title, "context_summary": context_summary})

    def create_node(self, parent_id, title, level_label, context_summary, labels=(), depends_on=None,
                    position=None):
        return self._call("POST", "/nodes", {
            "parent_id": parent_id, "title": title, "level_label": level_label,
            "context_summary": context_summary, "labels": list(labels),
            "depends_on": None if depends_on is None else list(depends_on), "position": position})

    def nodes_by_state(self, project_id, state):
        return self._call("GET", "/nodes", params={"project_id": project_id, "state": state})

    def get_node(self, node_id):
        return self._call("GET", f"/nodes/{node_id}")

    def children(self, node_id):
        return self._call("GET", f"/nodes/{node_id}/children")

    def ancestors(self, node_id):
        return self._call("GET", f"/nodes/{node_id}/ancestors")

    def ready_children(self, node_id):
        return self._call("GET", f"/nodes/{node_id}/ready-children")

    def update_node(self, node_id, **fields):
        return self._call("PATCH", f"/nodes/{node_id}", fields)

    def move_node(self, node_id, new_parent_id, position):
        return self._call("POST", f"/nodes/{node_id}/move", {"new_parent_id": new_parent_id, "position": position})

    def set_state(self, node_id, state):
        return self._call("POST", f"/nodes/{node_id}/state", {"state": state})

    def assign(self, node_id, agent_id, branch):
        return self._call("POST", f"/nodes/{node_id}/assign", {"agent_id": agent_id, "branch": branch})

    def create_supplementary_task(self, node_id, kind, title, context_summary):
        return self._call("POST", f"/nodes/{node_id}/supplementary",
                          {"kind": kind, "title": title, "context_summary": context_summary})

    def add_content(self, node_id, text, tags=()):
        return self._call("POST", f"/nodes/{node_id}/content", {"text": text, "tags": list(tags)})

    def replace_content(self, node_id, reference_id, text):
        return self._call("PUT", f"/nodes/{node_id}/content/{reference_id}", {"text": text})

    def context(self, node_id):
        return self._call("GET", f"/nodes/{node_id}/context")

    def reader_load(self, *, url=None, file_path=None, search_terms=None, strategy=None, line_start=None,
                    line_count=None):
        body = {"url": url, "search_terms": search_terms, "strategy": strategy,
                "line_start": line_start, "line_count": line_count}
        if file_path is not None:
            path = Path(file_path)
            body.update(file_name=path.name, file_base64=base64.b64encode(path.read_bytes()).decode("ascii"))
        return self._call("POST", "/reader/load", {k: v for k, v in body.items() if v is not None})

    def reader_toc(self, reader_id):
        return self._call("GET", f"/reader/{reader_id}/toc")

    def reader_get(self, reader_id, **params):
        return self._call("GET", f"/reader/{reader_id}/get", params=params)

    def reader_search(self, terms, ids=(), **opts):
        return self._call("POST", "/reader/search", {"terms": terms, "ids": list(ids), **opts})

    def reader_json(self, reader_id, flags):
        return self._call("POST", f"/reader/{reader_id}/json", {"flags": list(flags)})

    def reader_lines(self, reader_id, start, end):
        return self._call("GET", f"/reader/{reader_id}/lines", params={"start": start, "end": end})

    def reader_cite(self, reader_id, start_line, end_line):
        return self._call("POST", "/reader/cite", {"id": reader_id, "start_line": start_line, "end_line": end_line})

    def get_reference(self, reference_id):
        return self._call("GET", f"/references/{reference_id}")

    def reference_lines(self, reference_id, start=None, end=None):
        return self._call("GET", f"/references/{reference_id}/lines", params={"start": start, "end": end})

    def render_citation(self, citation):
        return self._call("POST", "/references/render", {"citation": citation})

    def store_user_exchange(self, session_id, user_message, pre_text):
        return self._call("POST", "/references/user-exchange",
                          {"session_id": session_id, "user_message": user_message, "pre_text": pre_text})

    def open_items(self, project_id):
        return self._call("GET", f"/projects/{project_id}/open-items")

    def search_references(self, query, limit=10):
        return self._call("GET", "/references/search", params={"q": query, "limit": limit})

    def propose_supersede(self, project_id, old_reference_id, new_reference_id, reason=""):
        return self._call("POST", "/supersede-candidates", {"project_id": project_id,
                                                           "old_reference_id": old_reference_id,
                                                           "new_reference_id": new_reference_id, "reason": reason})

    def supersede_candidates(self, project_id, status=None):
        return self._call("GET", "/supersede-candidates", params={"project_id": project_id, "status": status})

    def confirm_supersede(self, candidate_id):
        return self._call("POST", f"/supersede-candidates/{candidate_id}/confirm")

    def reject_supersede(self, candidate_id, reason):
        return self._call("POST", f"/supersede-candidates/{candidate_id}/reject", {"reason": reason})

    def list_reviews(self, project_id, status=None, node_id=None):
        return self._call("GET", "/reviews", params={"project_id": project_id, "status": status, "node_id": node_id})

    def get_review(self, review_id):
        return self._call("GET", f"/reviews/{review_id}")

    def take_review(self, project_id):
        return self._call("POST", "/reviews/take", {"project_id": project_id}) or None

    def submit_review_verdict(self, review_id, passed, reason, suggested_title=None, findings=(), reviewed_with=None):
        body = {"passed": passed, "reason": reason, "suggested_title": suggested_title,
                "findings": list(findings or ())}
        if reviewed_with is not None:
            body["reviewed_with"] = reviewed_with
        return self._call("POST", f"/reviews/{review_id}/verdict", body)

    def release_review(self, review_id):
        return self._call("POST", f"/reviews/{review_id}/release")

    def halt_server(self, project_id=None, reason=""):
        return self._call("POST", "/admin/halt", {"project_id": project_id, "reason": reason})

    def unhalt_server(self, project_id=None):
        return self._call("POST", "/admin/unhalt", {"project_id": project_id})

    def halt_status(self):
        return self._call("GET", "/admin/halt")

    def guidance(self, role):
        return self._call("GET", f"/guidance/{role}")

    def guidance_templates(self):
        return self._call("GET", "/guidance/templates")

    def guidance_rules(self):
        return self._call("GET", "/guidance/rules")


# --------------------------------------------------------------------------- recording client

def _recorder(name: str, signature: inspect.Signature) -> Callable:
    def method(self, *args, **kwargs):
        bound = signature.bind(self, *args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        arguments.pop("self")
        for var_kw in [p.name for p in signature.parameters.values() if p.kind is p.VAR_KEYWORD]:
            arguments.update(arguments.pop(var_kw, {}))
        self.calls.append((name, arguments))
        if self.raise_error is not None:
            raise self.raise_error
        return self.responses.get(name, {"called": name})
    method.__name__ = name
    return method


def _build_recording_client() -> type:
    namespace: dict = {}
    for name, member in vars(PlanningApiClientInterface).items():
        if getattr(member, "__isabstractmethod__", False) and callable(member):
            namespace[name] = _recorder(name, inspect.signature(member))

    def __init__(self, settings: Optional[ClientSettings] = None, raise_error: Optional[Exception] = None,
                 responses: Optional[dict] = None):
        self.settings = settings or ClientSettings()
        self.calls: list = []
        self.raise_error = raise_error
        self.responses = dict(responses or {})

    namespace["__init__"] = __init__
    namespace["with_token"] = lambda self, token: self
    namespace["tls_verify"] = property(lambda self: True)
    namespace["__doc__"] = "Records (method, arguments) for every call; returns {'called': name}."
    return type("RecordingPlanningApiClient", (PlanningApiClientInterface,), namespace)


RecordingPlanningApiClient = _build_recording_client()
