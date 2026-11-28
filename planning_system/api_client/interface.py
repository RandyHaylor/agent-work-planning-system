"""Public interface of api_client: one thin method per route in planning/BUILD-PLAN.md.

Responses are plain dicts/lists (the server's JSON). Errors: contract NotFound / Forbidden / Invalid
for 404 / 403 / 422, ApiError for any other failure status.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

Json = Union[dict, list]


class PlanningApiClientInterface(ABC):

    @abstractmethod
    def with_token(self, token: Optional[str]) -> "PlanningApiClientInterface":
        """Same settings and transport, different Bearer token."""

    @property
    @abstractmethod
    def tls_verify(self) -> Union[str, bool]:
        """What httpx `verify` is set to: the CA cert path; False only for localhost with no cert; else True."""

    # auth / identity
    @abstractmethod
    def start_admin_session(self, password: str) -> dict: ...          # POST /admin/sessions

    @abstractmethod
    def end_admin_session(self) -> dict: ...                           # DELETE /admin/sessions

    @abstractmethod
    def me(self) -> dict: ...                                          # GET /me

    @abstractmethod
    def mint_credential(self, role: str, project_id: int, scope_node_id: Optional[int],
                        agent_id: str) -> dict: ...                     # POST /credentials

    @abstractmethod
    def mint_quote_key(self, install_label: str) -> dict: ...          # POST /credentials/quote-key

    @abstractmethod
    def revoke_credential(self, credential_id: str) -> dict: ...       # POST /credentials/{id}/revoke

    @abstractmethod
    def rotate_credential(self, credential_id: str) -> dict: ...       # POST /credentials/{id}/rotate

    @abstractmethod
    def register_agent(self, agent_id: str, **metadata: Any) -> dict: ...  # POST /agents

    # tree
    @abstractmethod
    def create_project(self, title: str, context_summary: str) -> dict: ...  # POST /projects

    @abstractmethod
    def create_node(self, parent_id: int, title: str, level_label: str, context_summary: str,
                    labels: Sequence[str] = (), depends_on: Optional[Sequence[int]] = None,
                    position: Optional[int] = None) -> dict: ...       # POST /nodes

    @abstractmethod
    def nodes_by_state(self, project_id: int, state: str) -> list: ...  # GET /nodes?project_id=&state=

    @abstractmethod
    def get_node(self, node_id: int) -> dict: ...                      # GET /nodes/{id}

    @abstractmethod
    def children(self, node_id: int) -> list: ...                      # GET /nodes/{id}/children

    @abstractmethod
    def ancestors(self, node_id: int) -> list: ...                     # GET /nodes/{id}/ancestors

    @abstractmethod
    def ready_children(self, node_id: int) -> list: ...                # GET /nodes/{id}/ready-children

    @abstractmethod
    def update_node(self, node_id: int, **fields: Any) -> dict: ...    # PATCH /nodes/{id}

    @abstractmethod
    def move_node(self, node_id: int, new_parent_id: int, position: int) -> dict: ...  # POST /nodes/{id}/move

    @abstractmethod
    def set_state(self, node_id: int, state: str) -> dict: ...         # POST /nodes/{id}/state

    @abstractmethod
    def assign(self, node_id: int, agent_id: str, branch: str) -> dict: ...  # POST /nodes/{id}/assign

    @abstractmethod
    def create_supplementary_task(self, node_id: int, kind: str, title: str,
                                  context_summary: str) -> dict: ...   # POST /nodes/{id}/supplementary

    @abstractmethod
    def add_content(self, node_id: int, text: str, tags: Iterable[str] = ()) -> dict: ...  # POST /nodes/{id}/content

    @abstractmethod
    def replace_content(self, node_id: int, reference_id: str, text: str) -> dict: ...  # PUT /nodes/{id}/content/{ref}

    @abstractmethod
    def context(self, node_id: int) -> dict: ...                       # GET /nodes/{id}/context

    # reader + references
    @abstractmethod
    def reader_load(self, *, url: Optional[str] = None, file_path: Optional[Path] = None,
                    search_terms: Optional[str] = None, strategy: Optional[str] = None,
                    line_start: Optional[int] = None, line_count: Optional[int] = None) -> list:
        """POST /reader/load; file_path is read and sent as file_name + file_base64."""

    @abstractmethod
    def reader_toc(self, reader_id: str) -> Json: ...                  # GET /reader/{id}/toc

    @abstractmethod
    def reader_get(self, reader_id: str, **params: Any) -> Json: ...   # GET /reader/{id}/get

    @abstractmethod
    def reader_search(self, terms: str, ids: Sequence[str] = (), **opts: Any) -> Json: ...  # POST /reader/search

    @abstractmethod
    def reader_json(self, reader_id: str, flags: Sequence[str]) -> Json: ...  # POST /reader/{id}/json

    @abstractmethod
    def reader_lines(self, reader_id: str, start: int, end: int) -> Json: ...  # GET /reader/{id}/lines

    @abstractmethod
    def reader_cite(self, reader_id: str, start_line: int, end_line: int) -> dict: ...  # POST /reader/cite

    @abstractmethod
    def get_reference(self, reference_id: str) -> dict: ...  # GET /references/{id}: newest version (+ note)

    @abstractmethod
    def reference_lines(self, reference_id: str, start: Optional[int] = None,
                        end: Optional[int] = None) -> Json: ...        # GET /references/{id}/lines

    @abstractmethod
    def render_citation(self, citation: str) -> dict: ...              # POST /references/render

    @abstractmethod
    def store_user_exchange(self, session_id: str, user_message: str, pre_text: str) -> dict:
        """POST /references/user-exchange (quote key only)."""

    @abstractmethod
    def open_items(self, project_id: int) -> list: ...                 # GET /projects/{id}/open-items (log #61)

    # references search + supersede candidates (05-spec-reference-supersede.md)
    @abstractmethod
    def search_references(self, query: str, limit: int = 10) -> list: ...       # GET /references/search

    @abstractmethod
    def propose_supersede(self, project_id: int, old_reference_id: str, new_reference_id: str,
                          reason: str = "") -> dict: ...                       # POST /supersede-candidates

    @abstractmethod
    def supersede_candidates(self, project_id: int, status: Optional[str] = None) -> list: ...

    @abstractmethod
    def confirm_supersede(self, candidate_id: str) -> dict: ...      # POST /supersede-candidates/{id}/confirm

    @abstractmethod
    def reject_supersede(self, candidate_id: str, reason: str) -> dict: ...   # .../{id}/reject

    # content reviews (05-spec-citation-enforcement-and-review.md "Routes")
    @abstractmethod
    def list_reviews(self, project_id: int, status: Optional[str] = None,
                     node_id: Optional[int] = None) -> list: ...       # GET /reviews?project_id=&status=&node_id=

    @abstractmethod
    def get_review(self, review_id: str) -> dict: ...                  # GET /reviews/{id}

    @abstractmethod
    def take_review(self, project_id: int) -> Optional[dict]:
        """POST /reviews/take: the review packet, or None when nothing is pending (204)."""

    @abstractmethod
    def submit_review_verdict(self, review_id: str, passed: bool, reason: str,
                              suggested_title: Optional[str] = None,
                              findings: Sequence[str] = ()) -> dict: ...   # POST /reviews/{id}/verdict

    @abstractmethod
    def release_review(self, review_id: str) -> dict: ...              # POST /reviews/{id}/release

    # guidance
    @abstractmethod
    def guidance(self, role: str) -> dict: ...                         # GET /guidance/{role}

    @abstractmethod
    def guidance_templates(self) -> Json: ...                          # GET /guidance/templates

    @abstractmethod
    def guidance_rules(self) -> Json: ...                              # GET /guidance/rules
