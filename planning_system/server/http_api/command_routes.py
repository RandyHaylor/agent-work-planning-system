"""command_routes: the core routes (commands.catalog.CORE_ROUTES). Each handler only reads the request,
builds a command, runs it through the CommandRunner and returns JSON. No domain call, no SQL."""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from planning_system.contract import Principal
from planning_system.server import commands as C
from planning_system.server.http_api.dependencies import command_runner, current_principal
from planning_system.server.http_api import response_shapes as shapes
from planning_system.server.http_api.json_encoding import to_json

router = APIRouter(tags=["core"])

Who = Depends(current_principal)
Runner = Depends(command_runner)


# ---- request bodies (protocol only)

class PasswordBody(BaseModel):
    password: str


class MintBody(BaseModel):
    role: str
    project_id: Optional[int] = None
    scope_node_id: Optional[int] = None
    agent_id: Optional[str] = None


class QuoteKeyBody(BaseModel):
    install_label: str


class AgentBody(BaseModel):
    agent_id: str
    host: Optional[str] = None
    platform: Optional[str] = None
    model: Optional[str] = None
    path: Optional[str] = None
    system: Optional[str] = None
    url: Optional[str] = None


class ProjectBody(BaseModel):
    title: str
    context_summary: str


class NodeBody(BaseModel):
    parent_id: int
    title: str
    level_label: str
    context_summary: str
    labels: list[str] = Field(default_factory=list)
    depends_on: Optional[list[int]] = None
    position: Optional[int] = None


class NodePatch(BaseModel):
    title: Optional[str] = None
    level_label: Optional[str] = None
    context_summary: Optional[str] = None
    labels: Optional[list[str]] = None
    depends_on: Optional[list[int]] = None
    branch: Optional[str] = None


class MoveBody(BaseModel):
    new_parent_id: Optional[int]
    position: int


class StateBody(BaseModel):
    state: str


class AssignBody(BaseModel):
    agent_id: str
    branch: str


class SupplementaryBody(BaseModel):
    kind: str
    title: str
    context_summary: str


class ContentBody(BaseModel):
    text: str
    tags: list[str] = Field(default_factory=list)


class ReplaceContentBody(BaseModel):
    text: str
    tags: Optional[list[str]] = None          # None keeps the old item's tags


class TakeReviewBody(BaseModel):
    project_id: int


class VerdictBody(BaseModel):
    passed: bool
    reason: str
    suggested_title: Optional[str] = None
    findings: list[str] = Field(default_factory=list)   # quote checks: the earlier quotes the new one changes


class ProposeSupersedeBody(BaseModel):
    project_id: int
    old_reference_id: str
    new_reference_id: str
    reason: str = ""


class RejectSupersedeBody(BaseModel):
    reason: str


def _run(runner, command, principal: Optional[Principal], shape: Callable[[Any], Any] = to_json) -> Any:
    return to_json(shape(runner.run(command, principal)))


# ---- auth / identity

@router.post("/admin/sessions")
def start_admin_session(body: PasswordBody, runner=Runner):
    return _run(runner, C.StartAdminSession(body.password), None)


@router.delete("/admin/sessions")
def end_admin_session(principal: Principal = Who, runner=Runner):
    return _run(runner, C.EndAdminSession(), principal, shapes.ended)


@router.get("/me")
def me(principal: Principal = Who, runner=Runner):
    return _run(runner, C.GetCurrentPrincipal(), principal)


@router.post("/credentials")
def mint_credential(body: MintBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.MintCredential(body.role, body.project_id, body.scope_node_id, body.agent_id),
                principal)


@router.post("/credentials/quote-key")
def mint_quote_key(body: QuoteKeyBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.MintQuoteKey(body.install_label), principal)


@router.post("/credentials/{credential_id}/revoke")
def revoke_credential(credential_id: str, principal: Principal = Who, runner=Runner):
    return _run(runner, C.RevokeCredential(credential_id), principal, shapes.revoked(credential_id))


@router.post("/credentials/{credential_id}/rotate")
def rotate_credential(credential_id: str, principal: Principal = Who, runner=Runner):
    return _run(runner, C.RotateCredential(credential_id), principal, shapes.rotated)


@router.post("/agents")
def register_agent(body: AgentBody, principal: Principal = Who, runner=Runner):
    metadata = body.model_dump(exclude={"agent_id"}, exclude_none=True)
    return _run(runner, C.RegisterAgent(body.agent_id, metadata), principal)


# ---- tree

@router.post("/projects")
def create_project(body: ProjectBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.CreateProject(body.title, body.context_summary), principal)


@router.post("/nodes")
def create_node(body: NodeBody, principal: Principal = Who, runner=Runner):
    depends_on = None if body.depends_on is None else tuple(body.depends_on)
    return _run(runner, C.CreateNode(body.parent_id, body.title, body.level_label, body.context_summary,
                                     tuple(body.labels), depends_on, body.position), principal)


@router.get("/nodes")
def list_nodes_by_state(project_id: int, state: Optional[str] = None, principal: Principal = Who,
                        runner=Runner):
    return _run(runner, C.ListNodesByState(project_id, state), principal)


@router.get("/nodes/{node_id}")
def get_node(node_id: int, principal: Principal = Who, runner=Runner):
    return _run(runner, C.GetNode(node_id), principal)


@router.get("/nodes/{node_id}/children")
def list_children(node_id: int, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ListChildren(node_id), principal)


@router.get("/nodes/{node_id}/ancestors")
def list_ancestors(node_id: int, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ListAncestors(node_id), principal)


@router.get("/nodes/{node_id}/ready-children")
def list_ready_children(node_id: int, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ListReadyChildren(node_id), principal)


@router.patch("/nodes/{node_id}")
def update_node(node_id: int, body: NodePatch, principal: Principal = Who, runner=Runner):
    return _run(runner, C.UpdateNode(node_id, body.model_dump(exclude_unset=True)), principal)


@router.post("/nodes/{node_id}/move")
def move_node(node_id: int, body: MoveBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.MoveNode(node_id, body.new_parent_id, body.position), principal)


@router.post("/nodes/{node_id}/state")
def set_node_state(node_id: int, body: StateBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.SetNodeState(node_id, body.state), principal)


@router.post("/nodes/{node_id}/assign")
def assign_task(node_id: int, body: AssignBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.AssignTask(node_id, body.agent_id, body.branch), principal)


@router.post("/nodes/{node_id}/supplementary")
def create_supplementary_task(node_id: int, body: SupplementaryBody, principal: Principal = Who,
                              runner=Runner):
    return _run(runner, C.CreateSupplementaryTask(node_id, body.kind, body.title, body.context_summary),
                principal)


@router.post("/nodes/{node_id}/content")
def add_node_content(node_id: int, body: ContentBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.AddNodeContent(node_id, body.text, tuple(body.tags)), principal,
                shapes.node_content(node_id, body.text))


@router.put("/nodes/{node_id}/content/{reference_id}")
def replace_node_content(node_id: int, reference_id: str, body: ReplaceContentBody,
                         principal: Principal = Who, runner=Runner):
    tags = None if body.tags is None else tuple(body.tags)
    return _run(runner, C.ReplaceNodeContent(node_id, reference_id, body.text, tags), principal,
                shapes.node_content(node_id, body.text))


@router.get("/nodes/{node_id}/context")
def assemble_node_context(node_id: int, principal: Principal = Who, runner=Runner):
    return _run(runner, C.AssembleNodeContext(node_id), principal, shapes.assembled_context)


@router.get("/projects/{project_id}/open-items")
def list_open_items(project_id: int, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ListOpenItems(project_id), principal)


# ---- content review

@router.get("/reviews")
def list_reviews(project_id: int, status: Optional[str] = None, node_id: Optional[int] = None,
                 principal: Principal = Who, runner=Runner):
    return _run(runner, C.ListReviews(project_id, status, node_id), principal)


@router.post("/reviews/take")
def take_review(body: TakeReviewBody, principal: Principal = Who, runner=Runner):
    packet = runner.run(C.TakeReview(body.project_id), principal)
    if packet is None:
        return Response(status_code=204)          # nothing pending
    return to_json(packet)


@router.get("/reviews/{review_id}")
def get_review(review_id: str, principal: Principal = Who, runner=Runner):
    return _run(runner, C.GetReview(review_id), principal)


@router.post("/reviews/{review_id}/verdict")
def submit_review_verdict(review_id: str, body: VerdictBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.SubmitReviewVerdict(review_id, body.passed, body.reason, body.suggested_title,
                                              tuple(body.findings)), principal)


@router.post("/reviews/{review_id}/release")
def release_review(review_id: str, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReleaseReview(review_id), principal)


# ---- supersede candidates (05-spec-reference-supersede.md)

@router.post("/supersede-candidates")
def propose_supersede(body: ProposeSupersedeBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ProposeSupersede(body.project_id, body.old_reference_id, body.new_reference_id,
                                           body.reason), principal)


@router.get("/supersede-candidates")
def list_supersede_candidates(project_id: int, status: Optional[str] = None, principal: Principal = Who,
                              runner=Runner):
    return _run(runner, C.ListSupersedeCandidates(project_id, status), principal)


@router.post("/supersede-candidates/{candidate_id}/confirm")
def confirm_supersede(candidate_id: str, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ConfirmSupersede(candidate_id), principal)


@router.post("/supersede-candidates/{candidate_id}/reject")
def reject_supersede(candidate_id: str, body: RejectSupersedeBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.RejectSupersede(candidate_id, body.reason), principal)
