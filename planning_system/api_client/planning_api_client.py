"""PlanningApiClient: facade, one thin method per route; each builds the request and hands it to HttpTransport."""
from __future__ import annotations

import base64
import dataclasses
from pathlib import Path
from typing import Any, Optional, Union

import httpx

from .client_settings import tls_verify_for
from .http_transport import HttpTransport
from .interface import PlanningApiClientInterface
from .types import ClientSettings


class PlanningApiClient(PlanningApiClientInterface):

    def __init__(self, settings: ClientSettings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._http = HttpTransport(settings, transport)

    def with_token(self, token):
        return PlanningApiClient(dataclasses.replace(self._settings, token=token), self._http.raw_transport)

    @property
    def tls_verify(self) -> Union[str, bool]:
        return tls_verify_for(self._settings)

    def _call(self, method: str, path: str, json: Any = None, params: Optional[dict] = None) -> Any:
        return self._http.request(method, path, json=json, params=params)

    # auth / identity
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

    # tree
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

    # reader + references
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

    def get_reference(self, reference_id, follow_superseded=False):
        params = {"follow_superseded": "true"} if follow_superseded else None
        return self._call("GET", f"/references/{reference_id}", params=params)

    def reference_lines(self, reference_id, start=None, end=None):
        return self._call("GET", f"/references/{reference_id}/lines", params={"start": start, "end": end})

    def render_citation(self, citation):
        return self._call("POST", "/references/render", {"citation": citation})

    def store_user_exchange(self, session_id, user_message, pre_text):
        return self._call("POST", "/references/user-exchange",
                          {"session_id": session_id, "user_message": user_message, "pre_text": pre_text})

    # guidance
    def guidance(self, role):
        return self._call("GET", f"/guidance/{role}")

    def guidance_templates(self):
        return self._call("GET", "/guidance/templates")

    def guidance_rules(self):
        return self._call("GET", "/guidance/rules")
