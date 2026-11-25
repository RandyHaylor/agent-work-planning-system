"""init-and-register runs the install health check automatically and prints the
single confirmation line, then still registers the project."""
from __future__ import annotations

from source_of_truth import cli_entrypoint
from source_of_truth.install_health_check import run_install_health_check_quietly
from source_of_truth.requirements_tree_store import load_requirements_tree


def test_register_prints_health_check_line_and_registers(capsys):
    rc = cli_entrypoint._handle_init_and_register(["sess-health", "/tmp/s.jsonl"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Installation health check complete" in out
    # Registration still happened: the scaffolded tree is persisted.
    tree = load_requirements_tree("sess-health")
    assert tree.list_top_level_node_ids()  # default groups present


def test_health_check_is_idempotent_and_non_raising():
    # Runs to completion twice with no error; returns True (installer importable).
    assert run_install_health_check_quietly() is True
    assert run_install_health_check_quietly() is True
