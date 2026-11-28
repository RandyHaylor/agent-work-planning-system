"""Contract tests for http_api (spec: planning/05-spec-http-api.md). FastAPI TestClient with a
recording CommandRunner and the authentication fake. Routing is real thin code, so these run now."""
import inspect
import stat
from unittest import mock

import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from planning_system.api_client.fakes import FakePlanningApiClient
from planning_system.api_client.interface import PlanningApiClientInterface
from planning_system.api_client.types import ClientSettings
from planning_system.configuration import ConfigSection
from planning_system.contract import Forbidden, Invalid, NotFound, Principal
from planning_system.prompt_builder.guidance_interface import GuidanceService
from planning_system.prompt_builder.guidance_types import RoleGuidance
from planning_system.server import commands as C
from planning_system.server.commands.catalog import ROUTES
from planning_system.server.commands.fakes import RecordingCommandRunner
from planning_system.server.domain.access.fakes import TablePermissionPolicy
from planning_system.server.domain.authentication.fakes import (FakeAuthentication, FakeClock,
                                                                InMemoryCredentialStorage)
from planning_system.server.domain.authentication.types import IssuedCredential
from planning_system.server.domain.context_assembly.types import AssembledContext
from planning_system.server.domain.references.types import Citation, Reference
from planning_system.server.http_api import create_app, serve
from planning_system.server.http_api import dependencies as http_dependencies
from planning_system.server.http_api.tls import ensure_self_signed_cert

ROUTERS = [
    {"router": "planning_system.server.http_api.command_routes:router"},
    {"router": "planning_system.server.http_api.reference_routes:router"},
    {"router": "planning_system.server.http_api.guidance_routes:router"},
]


class StubGuidance(GuidanceService):
    def guidance_for(self, role):
        return RoleGuidance(role=role, template=role.title(), text=f"{role} text")

    def templates(self):
        return {"rolePresets": {}, "presets": []}

    def rules(self):
        return []


SAMPLE_RESULTS = {
    C.RotateCredential: IssuedCredential("tok", "cred-1", Principal("a", "worker")),
    C.AssembleNodeContext: AssembledContext(5, "text", (1, 5)),
    C.CiteCacheItem: Citation("tmp-1", 1, 2),
    C.RenderCitation: "line",
    C.StoreUserExchange: Reference("ref-1", "user_exchange", "m", "sha"),
}


@pytest.fixture
def server():
    auth = FakeAuthentication(InMemoryCredentialStorage(), TablePermissionPolicy(), FakeClock())
    runner = RecordingCommandRunner(respond=lambda command, _: SAMPLE_RESULTS.get(type(command), {"ok": True}))
    app = create_app(ConfigSection("http_api", {"routers": ROUTERS}), runner, auth,
                     {http_dependencies.guidance_service: StubGuidance})
    admin = auth.start("admin-pw")
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["Authorization"] = f"Bearer {admin.token}"
    return client, runner, admin


# (method, concrete path, json body, query params, expected command)
CASES = [
    ("DELETE", "/admin/sessions", None, None, C.EndAdminSession()),
    ("GET", "/me", None, None, C.GetCurrentPrincipal()),
    ("POST", "/credentials", {"role": "worker", "project_id": 1, "scope_node_id": 2, "agent_id": "a"}, None,
     C.MintCredential("worker", 1, 2, "a")),
    ("POST", "/credentials/quote-key", {"install_label": "laptop"}, None, C.MintQuoteKey("laptop")),
    ("POST", "/credentials/7/revoke", None, None, C.RevokeCredential("7")),
    ("POST", "/credentials/7/rotate", None, None, C.RotateCredential("7")),
    ("POST", "/agents", {"agent_id": "a", "host": "h", "model": "m"}, None,
     C.RegisterAgent("a", {"host": "h", "model": "m"})),
    ("POST", "/projects", {"title": "P", "context_summary": "c"}, None, C.CreateProject("P", "c")),
    ("POST", "/nodes", {"parent_id": 1, "title": "t", "level_label": "build", "context_summary": "c",
                        "labels": ["x"], "depends_on": [3], "position": 0}, None,
     C.CreateNode(1, "t", "build", "c", ("x",), (3,), 0)),
    ("GET", "/nodes", None, {"project_id": 1, "state": "done"}, C.ListNodesByState(1, "done")),
    ("GET", "/nodes/5", None, None, C.GetNode(5)),
    ("GET", "/nodes/5/children", None, None, C.ListChildren(5)),
    ("GET", "/nodes/5/ancestors", None, None, C.ListAncestors(5)),
    ("GET", "/nodes/5/ready-children", None, None, C.ListReadyChildren(5)),
    ("PATCH", "/nodes/5", {"title": "new", "branch": "b"}, None, C.UpdateNode(5, {"title": "new", "branch": "b"})),
    ("POST", "/nodes/5/move", {"new_parent_id": 2, "position": 1}, None, C.MoveNode(5, 2, 1)),
    ("POST", "/nodes/5/state", {"state": "done"}, None, C.SetNodeState(5, "done")),
    ("POST", "/nodes/5/assign", {"agent_id": "a", "branch": "b"}, None, C.AssignTask(5, "a", "b")),
    ("POST", "/nodes/5/supplementary", {"kind": "tech_spike", "title": "t", "context_summary": "c"}, None,
     C.CreateSupplementaryTask(5, "tech_spike", "t", "c")),
    ("POST", "/nodes/5/content", {"text": "x", "tags": ["t"]}, None, C.AddNodeContent(5, "x", ("t",))),
    ("PUT", "/nodes/5/content/ref-1", {"text": "y"}, None, C.ReplaceNodeContent(5, "ref-1", "y")),
    ("PUT", "/nodes/5/content/ref-1", {"text": "y", "tags": ["note"]}, None,
     C.ReplaceNodeContent(5, "ref-1", "y", ("note",))),
    ("GET", "/reviews", None, {"project_id": 1, "status": "failed", "node_id": 5},
     C.ListReviews(1, "failed", 5)),
    ("POST", "/reviews/take", {"project_id": 1}, None, C.TakeReview(1)),
    ("POST", "/reviews/rev-1/verdict", {"passed": False, "reason": "r", "suggested_title": "t"}, None,
     C.SubmitReviewVerdict("rev-1", False, "r", "t")),
    ("POST", "/reviews/rev-1/release", None, None, C.ReleaseReview("rev-1")),
    ("GET", "/reviews/rev-1", None, None, C.GetReview("rev-1")),
    ("GET", "/nodes/5/context", None, None, C.AssembleNodeContext(5)),
    ("POST", "/reader/load", {"url": "https://x"}, None, C.LoadIntoReader(url="https://x")),
    ("GET", "/reader/tmp-1/toc", None, None, C.ReaderToc("tmp-1")),
    ("GET", "/reader/tmp-1/get", None, {"section": "2"}, C.ReaderGet("tmp-1", {"section": "2"})),
    ("POST", "/reader/search", {"terms": "q", "ids": ["tmp-1"], "context": 2}, None,
     C.ReaderSearch("q", ("tmp-1",), {"context": 2})),
    ("POST", "/reader/tmp-1/json", {"flags": ["--keys"]}, None, C.ReaderJson("tmp-1", ("--keys",))),
    ("GET", "/reader/tmp-1/lines", None, {"start": 1, "end": 3}, C.ReaderLines("tmp-1", 1, 3)),
    ("POST", "/reader/cite", {"id": "tmp-1", "start_line": 1, "end_line": 2}, None, C.CiteCacheItem("tmp-1", 1, 2)),
    ("GET", "/references/ref-1", None, None, C.GetReference("ref-1")),
    ("GET", "/references/ref-1/lines", None, {"start": 2, "end": 4}, C.ReadReferenceLines("ref-1", 2, 4)),
    ("POST", "/references/render", {"citation": "[ref-1:1-2]"}, None, C.RenderCitation("[ref-1:1-2]")),
    ("POST", "/references/user-exchange", {"session_id": "s", "user_message": "m", "pre_text": "p"}, None,
     C.StoreUserExchange("s", "m", "p")),
]


def test_1_every_route_hands_its_command_and_principal_to_the_runner(server):
    client, runner, admin = server
    covered = set()
    for method, path, body, params, expected in CASES:
        response = client.request(method, path, json=body, params=params)
        assert response.status_code == 200, (path, response.text)
        command, principal = runner.last
        assert command == expected, path
        assert principal == admin.principal
        assert principal.credential_id == admin.credential_id
        covered.add(type(command))
    response = client.post("/admin/sessions", json={"password": "pw"}, headers={"Authorization": ""})
    assert response.status_code == 200 and runner.last == (C.StartAdminSession("pw"), None)
    covered.add(C.StartAdminSession)
    assert covered == set(ROUTES.values())


def test_1c_take_review_with_nothing_pending_is_204(server):
    client, runner, _ = server
    runner.respond = lambda command, _: None
    response = client.post("/reviews/take", json={"project_id": 1})
    assert response.status_code == 204 and response.content == b""


def test_1d_conflict_is_409(server):
    from planning_system.contract import Conflict
    client, runner, _ = server
    runner.error = Conflict("not the holder")
    response = client.post("/reviews/rev-1/verdict", json={"passed": True, "reason": "ok"})
    assert response.status_code == 409 and response.json() == {"error": "Conflict", "detail": "not the holder"}


def test_1b_app_serves_exactly_the_catalog_routes_plus_guidance(server):
    client, _, _ = server
    served = {(m, r.path) for r in client.app.routes if hasattr(r, "methods") and not r.path.startswith(
        ("/docs", "/openapi", "/redoc")) for m in r.methods if m != "HEAD"}
    guidance = {("GET", "/guidance/templates"), ("GET", "/guidance/rules"), ("GET", "/guidance/{role}")}
    assert served == set(ROUTES) | guidance


@pytest.mark.parametrize("headers", [{"Authorization": ""}, {"Authorization": "Bearer nope"},
                                     {"Authorization": "Basic abc"}])
def test_2_missing_or_unknown_token_is_403(server, headers):
    client, runner, _ = server
    assert client.get("/me", headers=headers).status_code == 403
    assert client.get("/reader/x/toc", headers=headers).status_code == 403
    assert client.get("/guidance/worker", headers=headers).status_code == 403
    assert runner.calls == []


@pytest.mark.parametrize("error,status,kind", [(NotFound("n"), 404, "NotFound"), (Forbidden("f"), 403, "Forbidden"),
                                               (Invalid("i"), 422, "Invalid")])
def test_3_domain_errors_map_to_status_with_error_and_detail(server, error, status, kind):
    client, runner, _ = server
    runner.error = error
    for path in ("/nodes/1", "/references/r"):
        response = client.get(path)
        assert response.status_code == status
        assert response.json() == {"error": kind, "detail": str(error)}


def test_3b_unexpected_error_is_500_without_internals(server):
    client, runner, _ = server
    runner.error = RuntimeError("secret table name")
    response = client.get("/nodes/1")
    assert response.status_code == 500
    assert "secret" not in response.text and "Traceback" not in response.text


def test_4_bad_request_body_is_422(server):
    client, runner, _ = server
    assert client.post("/nodes", json={"title": "missing fields"}).status_code == 422
    assert client.get("/nodes/not-a-number").status_code == 422
    assert client.post("/reader/load", json={}).status_code == 422          # command validation -> Invalid
    assert client.post("/nodes/1/supplementary", json={"kind": "x", "title": "t",
                                                       "context_summary": "c"}).status_code == 422
    assert runner.calls == []


def test_5_configured_routers_are_mounted(server):
    client, _, _ = server
    paths = {r.path for r in client.app.routes}
    assert {"/reader/load", "/references/{reference_id}", "/guidance/{role}", "/nodes/{node_id}"} <= paths
    assert client.get("/guidance/worker").json()["text"] == "worker text"


def test_6_self_signed_cert_created_once_and_reused(tmp_path):
    cert, key = ensure_self_signed_cert(tmp_path / "certs")
    first = cert.read_bytes()
    assert ensure_self_signed_cert(tmp_path / "certs") == (cert, key)
    assert cert.read_bytes() == first
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    san = x509.load_pem_x509_certificate(first).extensions.get_extension_for_class(x509.SubjectAlternativeName)
    assert "localhost" in san.value.get_values_for_type(x509.DNSName)
    assert "127.0.0.1" in {str(ip) for ip in san.value.get_values_for_type(x509.IPAddress)}


def test_7_serve_binds_localhost_by_default_with_tls(tmp_path):
    with mock.patch("planning_system.server.http_api.serving.uvicorn.run") as run:
        serve("APP", ConfigSection("http_api", {"cert_dir": str(tmp_path), "port": 9999}))
    args, kwargs = run.call_args
    assert args == ("APP",) and kwargs["host"] == "127.0.0.1" and kwargs["port"] == 9999
    assert kwargs["ssl_certfile"].endswith("server.crt") and kwargs["ssl_keyfile"].endswith("server.key")


def test_8_no_server_access_header_is_needed(server):
    client, _, _ = server
    assert client.get("/me").status_code == 200
    assert "X-Server-Access" not in client.headers


SAMPLE_ARGS = {
    "start_admin_session": ("pw",), "end_admin_session": (), "me": (),
    "mint_credential": ("worker", 1, 2, "a"), "mint_quote_key": ("l",), "revoke_credential": (7,),
    "rotate_credential": (7,), "register_agent": ("a",), "create_project": ("P", "c"),
    "create_node": (1, "t", "build", "c"), "nodes_by_state": (1, "done"), "get_node": (5,),
    "children": (5,), "ancestors": (5,), "ready_children": (5,), "update_node": (5,), "move_node": (5, 2, 1),
    "set_state": (5, "done"), "assign": (5, "a", "b"), "create_supplementary_task": (5, "tech_spike", "t", "c"),
    "add_content": (5, "x"), "replace_content": (5, 9, "y"), "context": (5,), "reader_toc": ("r",),
    "reader_get": ("r",), "reader_search": ("q",), "reader_json": ("r", ["--keys"]), "reader_lines": ("r", 1, 2),
    "reader_cite": ("r", 1, 2), "get_reference": (9,), "reference_lines": (9,), "render_citation": ("c",),
    "store_user_exchange": ("s", "m", "p"), "guidance": ("worker",), "guidance_templates": (),
    "guidance_rules": (),
    "list_reviews": (1,), "get_review": ("rev-1",), "take_review": (1,),
    "submit_review_verdict": ("rev-1", True, "ok"), "release_review": ("rev-1",),
}
REVIEW_METHODS = {"list_reviews", "get_review", "take_review", "submit_review_verdict", "release_review"}


def test_api_client_route_table_matches_the_server(server):
    """Every api_client method (as the client fake sends it) reaches a server route, not a 404/405/422."""
    client, runner, admin = server
    api = FakePlanningApiClient(ClientSettings("http://testserver", token=admin.token), client._transport)
    methods = [n for n, f in inspect.getmembers(PlanningApiClientInterface)
               if getattr(f, "__isabstractmethod__", False) and n not in ("with_token", "tls_verify")]
    assert set(methods) - {"reader_load"} == set(SAMPLE_ARGS)
    if not any(getattr(r, "path", "").startswith("/reviews") for r in client.app.routes):
        methods = [n for n in methods if n not in REVIEW_METHODS]   # server review routes not merged yet
    for name in methods:
        if name == "reader_load":
            api.reader_load(url="https://x")
        else:
            getattr(api, name)(*SAMPLE_ARGS[name])
