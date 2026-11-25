"""External integration tests for api_client (planning/05-spec-api-client.md), run on [fake, real]."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx
import pytest

from planning_system.api_client import ApiError, ClientSettings, PlanningApiClient
from planning_system.api_client.fakes import FakePlanningApiClient, FakePlanningServer
from planning_system.contract import Forbidden, Invalid, NotFound

BASE_URL = "https://127.0.0.1:8443"

IMPLEMENTATIONS = [
    pytest.param(FakePlanningApiClient, id="fake"),
    pytest.param(PlanningApiClient, id="real"),
]


@pytest.fixture(params=IMPLEMENTATIONS)
def client_class(request):
    return request.param


@pytest.fixture
def server():
    return FakePlanningServer()


@pytest.fixture
def admin_token(server):
    return server.issue_token("admin")


@pytest.fixture
def client(client_class, server, admin_token):
    return client_class(ClientSettings(BASE_URL, None, admin_token), transport=server.transport())


@pytest.fixture
def project(server):
    project = server.seed_project()
    task = server._new_node(project["id"], "Task", "task", "do it", [], None)
    return {"project": project["id"], "task": task["id"]}


# (call, expected HTTP method, expected path, expected JSON body or None for "no body check")
def _route_cases(ids):
    p, t = ids["project"], ids["task"]
    return [
        (lambda c: c.me(), "GET", "/me", None),
        (lambda c: c.end_admin_session(), "DELETE", "/admin/sessions", None),
        (lambda c: c.mint_credential("worker", p, t, "agent-1"), "POST", "/credentials",
         {"role": "worker", "project_id": p, "scope_node_id": t, "agent_id": "agent-1"}),
        (lambda c: c.mint_quote_key("laptop"), "POST", "/credentials/quote-key", {"install_label": "laptop"}),
        (lambda c: c.revoke_credential(7), "POST", "/credentials/7/revoke", None),
        (lambda c: c.rotate_credential(7), "POST", "/credentials/7/rotate", None),
        (lambda c: c.register_agent("agent-1", host="h", model="m"), "POST", "/agents",
         {"agent_id": "agent-1", "host": "h", "model": "m"}),
        (lambda c: c.create_project("T", "S"), "POST", "/projects", {"title": "T", "context_summary": "S"}),
        (lambda c: c.create_node(p, "N", "task", "S", labels=["x"], depends_on=[t], position=0), "POST", "/nodes",
         {"parent_id": p, "title": "N", "level_label": "task", "context_summary": "S", "labels": ["x"],
          "depends_on": [t], "position": 0}),
        (lambda c: c.nodes_by_state(p, "open"), "GET", "/nodes", None),
        (lambda c: c.get_node(t), "GET", f"/nodes/{t}", None),
        (lambda c: c.children(p), "GET", f"/nodes/{p}/children", None),
        (lambda c: c.ancestors(t), "GET", f"/nodes/{t}/ancestors", None),
        (lambda c: c.ready_children(p), "GET", f"/nodes/{p}/ready-children", None),
        (lambda c: c.update_node(t, title="New"), "PATCH", f"/nodes/{t}", {"title": "New"}),
        (lambda c: c.move_node(t, p, 1), "POST", f"/nodes/{t}/move", {"new_parent_id": p, "position": 1}),
        (lambda c: c.set_state(t, "done"), "POST", f"/nodes/{t}/state", {"state": "done"}),
        (lambda c: c.assign(t, "agent-1", "feat/x"), "POST", f"/nodes/{t}/assign",
         {"agent_id": "agent-1", "branch": "feat/x"}),
        (lambda c: c.create_supplementary_task(t, "tech_spike", "Spike", "S"), "POST", f"/nodes/{t}/supplementary",
         {"kind": "tech_spike", "title": "Spike", "context_summary": "S"}),
        (lambda c: c.add_content(t, "done it", ["verdict"]), "POST", f"/nodes/{t}/content",
         {"text": "done it", "tags": ["verdict"]}),
        (lambda c: c.replace_content(t, 9, "v2"), "PUT", f"/nodes/{t}/content/9", {"text": "v2"}),
        (lambda c: c.context(t), "GET", f"/nodes/{t}/context", None),
        (lambda c: c.reader_load(url="https://example.com"), "POST", "/reader/load", {"url": "https://example.com"}),
        (lambda c: c.reader_load(search_terms="x y"), "POST", "/reader/load", {"search_terms": "x y"}),
        (lambda c: c.reader_toc("c1"), "GET", "/reader/c1/toc", None),
        (lambda c: c.reader_get("c1", section="2"), "GET", "/reader/c1/get", None),
        (lambda c: c.reader_search("foo", ["c1"]), "POST", "/reader/search", {"terms": "foo", "ids": ["c1"]}),
        (lambda c: c.reader_json("c1", ["--keys"]), "POST", "/reader/c1/json", {"flags": ["--keys"]}),
        (lambda c: c.reader_lines("c1", 1, 5), "GET", "/reader/c1/lines", None),
        (lambda c: c.reader_cite("c1", 1, 5), "POST", "/reader/cite", {"id": "c1", "start_line": 1, "end_line": 5}),
        (lambda c: c.reference_lines(3, 1, 2), "GET", "/references/3/lines", None),
        (lambda c: c.render_citation("[c1:1-5]"), "POST", "/references/render", {"citation": "[c1:1-5]"}),
        (lambda c: c.guidance("worker"), "GET", "/guidance/worker", None),
        (lambda c: c.guidance_templates(), "GET", "/guidance/templates", None),
        (lambda c: c.guidance_rules(), "GET", "/guidance/rules", None),
    ]


ROUTE_CASE_COUNT = 35


@pytest.mark.parametrize("case_index", range(ROUTE_CASE_COUNT))
def test_1_each_method_sends_documented_route_with_bearer(client, server, project, admin_token, case_index):
    call, method, path, body = _route_cases(project)[case_index]
    try:
        call(client)
    except NotFound:
        pass  # the fake server may not hold the referenced object; the request is what we check
    sent = server.requests[-1]
    assert (sent.method, sent.path) == (method, path)
    assert sent.headers["authorization"] == f"Bearer {admin_token}"
    if body is not None:
        assert sent.body == body


def test_1_query_parameters(client, server, project):
    client.nodes_by_state(project["project"], "open")
    assert server.requests[-1].params == {"project_id": str(project["project"]), "state": "open"}
    client.reader_lines("c1", 1, 5)
    assert server.requests[-1].params == {"start": "1", "end": "5"}


def test_1_admin_session_and_quote_exchange(client_class, server):
    anonymous = client_class(ClientSettings(BASE_URL), transport=server.transport())
    token = anonymous.start_admin_session("correct horse")["token"]
    assert server.requests[-1].body == {"password": "correct horse"}
    quote_client = anonymous.with_token(server.issue_token("quote_client"))
    first = quote_client.store_user_exchange("s1", "hello", "pre")
    assert (server.requests[-1].method, server.requests[-1].path) == ("POST", "/references/user-exchange")
    assert quote_client.get_reference(first["reference_id"])["user_message"] == "hello"
    assert token


@pytest.mark.parametrize("status, error_type, call", [
    (404, NotFound, lambda c: c.get_node(999_999)),
    (403, Forbidden, lambda c: c.with_token("not-a-token").me()),
    (422, Invalid, lambda c: c.set_state(1, "not-a-state")),
])
def test_2_contract_errors(client, server, status, error_type, call):
    server.seed_project()
    with pytest.raises(error_type):
        call(client)


def test_2_other_status_raises_api_error_with_body(client, server):
    server.fail_next(500, {"detail": "boom"})
    with pytest.raises(ApiError) as caught:
        client.me()
    assert caught.value.status == 500
    assert caught.value.body == {"detail": "boom"}


def test_3_tls_verify_uses_configured_cert(client_class, server, tmp_path):
    cert = tmp_path / "server.pem"
    assert client_class(ClientSettings(BASE_URL, cert, "t")).tls_verify == str(cert)
    assert client_class(ClientSettings("https://127.0.0.1:8443", None, "t")).tls_verify is False
    assert client_class(ClientSettings("https://planning.example.com", None, "t")).tls_verify is True


def test_4_reader_load_file_sends_exact_bytes_and_name(client, server, tmp_path):
    data = bytes(range(256)) * 3
    file_path = tmp_path / "notes.bin"
    file_path.write_bytes(data)
    client.reader_load(file_path=file_path)
    body = server.requests[-1].body
    assert body["file_name"] == "notes.bin"
    assert base64.b64decode(body["file_base64"]) == data


def test_5_token_never_logged_or_in_errors(client, server, admin_token, caplog):
    caplog.set_level(logging.DEBUG)
    for status in (500, 404, 403, 422):
        server.fail_next(status, {"detail": "nope"})
        with pytest.raises((ApiError, NotFound, Forbidden, Invalid)) as caught:
            client.me()
        assert admin_token not in str(caught.value)
        assert admin_token not in repr(caught.value.args)
    assert admin_token not in caplog.text
    assert admin_token not in repr(ClientSettings(BASE_URL, None, admin_token))


def test_6_round_trips_me_against_fastapi_testclient(client_class):
    from fastapi import FastAPI, Header
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/me")
    def me(authorization: str = Header(...)):
        return {"role": "admin", "token_seen": authorization == "Bearer abc"}

    transport = TestClient(app)._transport
    client = client_class(ClientSettings("http://testserver", None, "abc"), transport=transport)
    assert client.me() == {"role": "admin", "token_seen": True}
