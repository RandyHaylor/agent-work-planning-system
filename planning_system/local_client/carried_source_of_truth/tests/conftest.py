"""Shared fixtures: redirect the SoT root to a tmp dir so tests never touch the real ~/.source-of-truth."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture(autouse=True)
def isolated_source_of_truth_root(tmp_path, monkeypatch):
    from source_of_truth import load_config as config_module

    isolated_root_dir = tmp_path / ".source-of-truth"
    isolated_projects_dir = isolated_root_dir / "projects"
    monkeypatch.setattr(config_module, "SOURCE_OF_TRUTH_ROOT_DIR", isolated_root_dir)
    monkeypatch.setattr(config_module, "GLOBAL_SETTINGS_FILE_PATH", isolated_root_dir / "global-settings.json")
    monkeypatch.setattr(config_module, "PROJECTS_PARENT_DIR", isolated_projects_dir)
    # Also redirect HOME so the standalone resolver script picks up the same tree.
    monkeypatch.setenv("HOME", str(tmp_path))
    isolated_root_dir.mkdir(parents=True, exist_ok=True)
    isolated_projects_dir.mkdir(parents=True, exist_ok=True)
    yield isolated_root_dir
