"""Contract tests for configuration + main.py (spec: planning/05-spec-configuration.md). Real code."""
import ast
import json
import sys
import types
from pathlib import Path

import pytest

from planning_system import main as main_module
from planning_system.configuration import load_component, load_configuration
from planning_system.contract import Invalid

REPO = Path(__file__).resolve().parents[3]


def write(folder: Path, name: str, data) -> None:
    (folder / name).write_text(json.dumps(data))


@pytest.fixture
def fake_component_module(monkeypatch):
    """A module `fake_components` with a factory recording the section it got."""
    module = types.ModuleType("fake_components")
    module.seen = []

    class Component:
        def __init__(self, section):
            self.section = section

        def commands(self):
            return {"run": lambda args: 7, "hello": lambda args: 0}

    def factory(section):
        module.seen.append(section)
        return Component(section)

    module.factory = factory
    monkeypatch.setitem(sys.modules, "fake_components", module)
    return module


def test_1_two_files_load_into_one_configuration(tmp_path):
    write(tmp_path, "main.json", {"components": ["server"]})
    write(tmp_path, "server.json", {"server": {"storage": {"dsn": "postgresql://x"}}})
    config = load_configuration(tmp_path, environ={})
    assert config.section("server").child("storage").get("dsn") == "postgresql://x"
    assert config.top().get("components") == ["server"]


def test_2_env_substitution_environment_then_dotenv_then_error(tmp_path):
    folder = tmp_path / "config"
    folder.mkdir()
    write(folder, "s.json", {"s": {"a": "${A}", "b": "x-${B}-y", "n": 3}})
    (tmp_path / ".env").write_text("A=from-dotenv\nB='quoted'\n")
    assert load_configuration(folder, environ={"A": "from-env"}).section("s").as_dict() == {
        "a": "from-env", "b": "x-quoted-y", "n": 3}
    assert load_configuration(folder, environ={}).section("s").get("a") == "from-dotenv"
    (tmp_path / ".env").write_text("")
    with pytest.raises(Invalid, match="B"):
        load_configuration(folder, environ={"A": "1"})


def test_3_missing_section_names_it(tmp_path):
    write(tmp_path, "main.json", {"components": []})
    with pytest.raises(Invalid, match="nope"):
        load_configuration(tmp_path, environ={}).section("nope")


def test_3b_same_key_in_two_files_is_an_error(tmp_path):
    write(tmp_path, "a.json", {"x": {}})
    write(tmp_path, "b.json", {"x": {}})
    with pytest.raises(Invalid, match="x"):
        load_configuration(tmp_path, environ={})


def test_4_load_component_calls_factory_once_with_its_own_section(tmp_path, fake_component_module):
    write(tmp_path, "c.json", {"thing": {"factory": "fake_components:factory", "k": 1}, "other": {"secret": 2}})
    section = load_configuration(tmp_path, environ={}).section("thing")
    load_component(section)
    assert len(fake_component_module.seen) == 1
    got = fake_component_module.seen[0]
    assert got.as_dict() == {"factory": "fake_components:factory", "k": 1}
    assert not got.has("other") and not got.has("secret")


def test_5_main_runs_the_components_command(tmp_path, fake_component_module):
    write(tmp_path, "main.json", {"components": ["thing"]})
    write(tmp_path, "thing.json", {"thing": {"factory": "fake_components:factory"}})
    assert main_module.main(["--config", str(tmp_path), "run"]) == 7


def test_5b_main_imports_nothing_concrete():
    tree = ast.parse(Path(main_module.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    banned = ("planning_system.server", "fastapi", "sqlalchemy", "psycopg", "uvicorn")
    assert not [m for m in imported if m.startswith(banned)], imported


def test_6_unknown_command_lists_commands(tmp_path, fake_component_module, capsys):
    write(tmp_path, "main.json", {"components": ["thing"]})
    write(tmp_path, "thing.json", {"thing": {"factory": "fake_components:factory"}})
    assert main_module.main(["--config", str(tmp_path), "frobnicate"]) == 2
    err = capsys.readouterr().err
    assert "frobnicate" in err and "hello" in err and "run" in err


def test_shipped_config_names_the_server_component():
    config = load_configuration(REPO / "config", environ={"PLANNING_DSN": "postgresql+psycopg://x/planning_system"})
    assert config.top().get("components") == ["server"]
    server = config.section("server")
    assert server.get("factory") == "planning_system.server.composition:create_server"
    component = load_component(server)
    assert {"run", "bootstrap"} <= set(component.commands())
