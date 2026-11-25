"""cli contract (planning/05-spec-cli.md tests 1-6), on [fake, real]; api_client and local_client are recording fakes."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

import planning_system.cli as cli_package
from planning_system.api_client import ApiError, ClientSettings
from planning_system.api_client.fakes import RecordingPlanningApiClient
from planning_system.cli import CliDependencies, PlanningCommandLine
from planning_system.cli.fakes import FakeCommandLine
from planning_system.contract import Forbidden, Invalid, NotFound
from planning_system.local_client.fakes import RecordingLocalClient
from planning_system.local_client.task_runner import TaskStartRequest

ENV = {"PLANNING_TOKEN": "tok", "PLANNING_URL": "https://127.0.0.1:8443"}


class _FakeLogin:
    def login(self):
        return "admin-tok"


class Harness:
    def __init__(self, command_line_class, api_error=None):
        self.api = RecordingPlanningApiClient(raise_error=api_error, responses={"me": {"scope_node_id": 42}})
        self.local = RecordingLocalClient()
        self.editor_launches = 0
        self.command_line = command_line_class(CliDependencies(
            api_factory=lambda settings: self.api,
            local_client_factory=lambda settings: self.local,
            admin_login_factory=lambda api: _FakeLogin(),
            settings_from_environment=lambda env: ClientSettings(env.get("PLANNING_URL", "https://127.0.0.1:8443"),
                                                                 None, env.get("PLANNING_TOKEN")),
            launch_guidance_editor=self._launch))

    def _launch(self):
        self.editor_launches += 1

    def run(self, *argv, env=ENV):
        self.out, self.err = io.StringIO(), io.StringIO()
        return self.command_line.run(list(argv), env, self.out, self.err)


@pytest.fixture(params=[pytest.param(FakeCommandLine, id="fake"),
                        pytest.param(PlanningCommandLine, id="real")])
def command_line_class(request):
    return request.param


@pytest.fixture
def harness(command_line_class):
    return Harness(command_line_class)


SERVER_COMMANDS = [
    (["admin", "logout"], "end_admin_session", {}),
    (["me"], "me", {}),
    (["credentials", "mint", "--role", "worker", "--project", "1", "--scope", "5", "--agent", "a1"],
     "mint_credential", {"role": "worker", "project_id": 1, "scope_node_id": 5, "agent_id": "a1"}),
    (["credentials", "quote-key", "--label", "laptop"], "mint_quote_key", {"install_label": "laptop"}),
    (["credentials", "revoke", "7"], "revoke_credential", {"credential_id": 7}),
    (["credentials", "rotate", "7"], "rotate_credential", {"credential_id": 7}),
    (["agents", "register", "a1", "--host", "h", "--model", "m"], "register_agent",
     {"agent_id": "a1", "host": "h", "model": "m"}),
    (["projects", "create", "--title", "T", "--summary", "S"], "create_project",
     {"title": "T", "context_summary": "S"}),
    (["nodes", "create", "--parent", "1", "--title", "N", "--level", "task", "--summary", "S", "--labels", "a", "b",
      "--depends-on", "2", "3", "--position", "0"], "create_node",
     {"parent_id": 1, "title": "N", "level_label": "task", "context_summary": "S", "labels": ["a", "b"],
      "depends_on": [2, 3], "position": 0}),
    (["nodes", "list", "--project", "1", "--state", "open"], "nodes_by_state", {"project_id": 1, "state": "open"}),
    (["nodes", "get", "3"], "get_node", {"node_id": 3}),
    (["nodes", "children", "3"], "children", {"node_id": 3}),
    (["nodes", "ancestors", "3"], "ancestors", {"node_id": 3}),
    (["nodes", "ready", "3"], "ready_children", {"node_id": 3}),
    (["nodes", "update", "3", "--title", "New"], "update_node", {"node_id": 3, "title": "New"}),
    (["nodes", "move", "3", "--parent", "1", "--position", "2"], "move_node",
     {"node_id": 3, "new_parent_id": 1, "position": 2}),
    (["nodes", "state", "3", "done"], "set_state", {"node_id": 3, "state": "done"}),
    (["nodes", "context", "3"], "context", {"node_id": 3}),
    (["content", "add", "3", "--text", "hello", "--tags", "verdict"], "add_content",
     {"node_id": 3, "text": "hello", "tags": ["verdict"]}),
    (["content", "replace", "3", "9", "--text", "v2"], "replace_content",
     {"node_id": 3, "reference_id": 9, "text": "v2"}),
    (["task", "assign", "3", "--agent", "a1", "--branch", "feat/x"], "assign",
     {"node_id": 3, "agent_id": "a1", "branch": "feat/x"}),
    (["toc", "c1"], "reader_toc", {"reader_id": "c1"}),
    (["get", "c1", "--section", "2"], "reader_get", {"reader_id": "c1", "section": "2"}),
    (["search", "foo", "--ids", "c1", "c2"], "reader_search", {"terms": "foo", "ids": ["c1", "c2"]}),
    (["json", "c1", "--keys", "--depth", "2"], "reader_json", {"reader_id": "c1", "flags": ["--keys", "--depth", "2"]}),
    (["lines", "c1", "1", "5"], "reader_lines", {"reader_id": "c1", "start": 1, "end": 5}),
    (["cite", "c1", "1", "5"], "reader_cite", {"reader_id": "c1", "start_line": 1, "end_line": 5}),
    (["references", "get", "4", "--follow-superseded"], "get_reference", {"reference_id": 4, "follow_superseded": True}),
    (["references", "lines", "4", "--start", "1", "--end", "3"], "reference_lines",
     {"reference_id": 4, "start": 1, "end": 3}),
    (["references", "render", "[c1:1-5]"], "render_citation", {"citation": "[c1:1-5]"}),
    (["guidance", "worker"], "guidance", {"role": "worker"}),
    (["guidance", "planner"], "guidance", {"role": "planner"}),
    (["guidance", "templates"], "guidance_templates", {}),
    (["guidance", "rules"], "guidance_rules", {}),
]


def _sent(api, name):
    return [(n, {k: v for k, v in a.items()}) for n, a in api.calls if n == name]


@pytest.mark.parametrize("argv, method, expected", SERVER_COMMANDS, ids=lambda v: " ".join(v) if isinstance(v, list) else None)
def test_1_each_server_command_calls_one_api_method_and_prints_json(harness, argv, method, expected):
    assert harness.run(*argv) == 0
    assert len(harness.api.calls) == 1
    name, arguments = harness.api.calls[0]
    assert name == method
    assert {k: v for k, v in arguments.items() if v not in (None, (), [])} == \
        {k: v for k, v in expected.items() if v not in (None, (), [])}
    assert json.loads(harness.out.getvalue()) == harness.api.responses.get(method, {"called": method})
    assert harness.local.calls == []


def test_1_supplementary_targets_own_task_from_me(harness):
    assert harness.run("supplementary", "create", "--kind", "tech_spike", "--title", "S", "--summary", "x") == 0
    assert harness.api.calls[-1] == ("create_supplementary_task",
                                     {"node_id": 42, "kind": "tech_spike", "title": "S", "context_summary": "x"})


def test_1_admin_login_prints_token(harness):
    assert harness.run("admin", "login", env={}) == 0
    assert "PLANNING_TOKEN=admin-tok" in harness.out.getvalue()


@pytest.mark.parametrize("argv, method", [
    (["task", "stop", "a1"], "stop_task"),
    (["task", "list"], "running_tasks"),
    (["review", "ask", "is it ok?", "--context", "a.py"], "ask_reviewer"),
    (["client", "install-hooks"], "install_hooks"),
    (["client", "exchanges", "--last", "3"], "list_exchanges"),
])
def test_1_local_commands_call_local_client_only(harness, argv, method):
    assert harness.run(*argv) == 0
    assert [name for name, _ in harness.local.calls] == [method]
    assert harness.api.calls == []


def test_1_task_start_builds_request(harness):
    assert harness.run("task", "start", "3", "--agent", "a1", "--token", "wt", "--dir", "/w", "--role", "planner") == 0
    name, arguments = harness.local.calls[0]
    assert name == "start_task"
    assert arguments["request"] == TaskStartRequest(3, "a1", "planner", "wt", Path("/w"))


@pytest.mark.parametrize("error", [NotFound("no node 9"), Forbidden("nope"), Invalid("bad state"),
                                   ApiError(500, {"detail": "boom"})])
def test_2_contract_errors_exit_1_with_message_on_stderr(command_line_class, error):
    harness = Harness(command_line_class, api_error=error)
    assert harness.run("nodes", "get", "9") == 1
    assert harness.err.getvalue().strip()
    assert harness.out.getvalue() == ""


@pytest.mark.parametrize("argv", [["nodes", "get"], ["nodes", "get", "not-an-int"], ["no-such-command"], []])
def test_2_bad_usage_exits_2(harness, argv):
    assert harness.run(*argv) == 2
    assert harness.api.calls == []


def test_3_missing_token_fails_before_any_request(harness):
    assert harness.run("me", env={"PLANNING_URL": "https://127.0.0.1:8443"}) != 0
    assert "PLANNING_TOKEN" in harness.err.getvalue()
    assert harness.api.calls == []


def test_4_cite_exchange_calls_reference_sync_only(harness):
    assert harness.run("cite-exchange", "x1") == 0
    assert harness.local.calls == [("cite_exchange", {"local_exchange_id": "x1"})]
    assert harness.api.calls == []


def test_5_load_file_sends_file_and_url_sends_url(harness, tmp_path):
    file_path = tmp_path / "doc.md"
    file_path.write_text("# hi")
    assert harness.run("load", str(file_path)) == 0
    assert harness.run("load", "https://example.com/page") == 0
    assert harness.run("load", "--search", "postgres locks") == 0
    calls = [arguments for name, arguments in harness.api.calls if name == "reader_load"]
    assert Path(calls[0]["file_path"]) == file_path and calls[0].get("url") is None
    assert calls[1]["url"] == "https://example.com/page" and calls[1].get("file_path") is None
    assert calls[2]["search_terms"] == "postgres locks"


def test_6_no_branching_on_roles_or_states():
    cli_dir = Path(cli_package.__file__).parent
    pattern = re.compile(r"^\s*(if|elif|match)\b.*\b(role|state)s?\b", re.MULTILINE)
    offenders = {path.name: pattern.findall(path.read_text()) for path in cli_dir.glob("*.py")}
    assert {name: hits for name, hits in offenders.items() if hits} == {}


def test_guidance_editor_launches_locally(harness):
    assert harness.run("guidance-editor", env={}) == 0
    assert harness.editor_launches == 1
    assert harness.api.calls == []
