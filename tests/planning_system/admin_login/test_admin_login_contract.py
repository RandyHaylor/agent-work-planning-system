"""External integration tests for admin_login (planning/05-spec-admin-login.md): mocked server + fake prompt."""
from __future__ import annotations

import logging

import pytest

from planning_system.admin_login import AdminLoginFlow, LoginCancelled, LoginFailed, NoDisplay
from planning_system.admin_login.fakes import FakeAdminLoginFlow, FakePasswordPrompt
from planning_system.api_client import ClientSettings
from planning_system.api_client.fakes import FakePlanningApiClient, FakePlanningServer

PASSWORD = "correct horse"
WRONG = "s3cret-wrong-guess"

IMPLEMENTATIONS = [
    pytest.param(FakeAdminLoginFlow, id="fake"),
    pytest.param(AdminLoginFlow, id="real", marks=pytest.mark.xfail(strict=False, reason="level 7")),
]


@pytest.fixture(params=IMPLEMENTATIONS)
def flow_class(request):
    return request.param


@pytest.fixture
def server():
    return FakePlanningServer(admin_password=PASSWORD)


@pytest.fixture
def api(server):
    return FakePlanningApiClient(ClientSettings(), transport=server.transport())


def _session_posts(server):
    return [r for r in server.requests if (r.method, r.path) == ("POST", "/admin/sessions")]


def test_1_correct_password_posts_once_and_returns_token(flow_class, server, api):
    token = flow_class(api, FakePasswordPrompt([PASSWORD])).login()
    posts = _session_posts(server)
    assert len(posts) == 1 and posts[0].body == {"password": PASSWORD}
    assert token in server.tokens and server.tokens[token]["role"] == "admin"


def test_2_wrong_password_asks_again_then_fails_after_three(flow_class, server, api):
    prompt = FakePasswordPrompt([WRONG, PASSWORD])
    assert flow_class(api, prompt).login()
    assert len(prompt.asked) == 2
    with pytest.raises(LoginFailed):
        flow_class(api, FakePasswordPrompt([WRONG, WRONG, WRONG, PASSWORD])).login()


def test_3_cancel_sends_nothing(flow_class, server, api):
    with pytest.raises(LoginCancelled):
        flow_class(api, FakePasswordPrompt([None])).login()
    assert server.requests == []


def test_4_no_display_sends_nothing_and_never_reads_terminal(flow_class, server, api, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("terminal prompt used"))
    with pytest.raises(NoDisplay):
        flow_class(api, FakePasswordPrompt(display=False)).login()
    assert server.requests == []


def test_5_password_never_in_logs_exceptions_or_stdout(flow_class, server, api, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(LoginFailed) as caught:
        flow_class(api, FakePasswordPrompt([WRONG] * 3)).login()
    assert WRONG not in str(caught.value)
    assert WRONG not in caplog.text
    out = capsys.readouterr()
    assert WRONG not in out.out and WRONG not in out.err
