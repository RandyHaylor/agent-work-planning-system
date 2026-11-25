from __future__ import annotations

import json

from source_of_truth import load_config as config_module
from source_of_truth.load_config import (
    DEFAULT_REVIEWER_MODEL_NAME,
    GlobalSettings,
    load_global_settings,
    load_project_settings,
    resolve_reviewer_model_name_for_project,
    save_global_settings,
    save_project_settings,
    write_default_global_settings_if_absent,
)


def test_default_reviewer_model_is_haiku_when_no_settings_file():
    assert load_global_settings().reviewer_model_name == DEFAULT_REVIEWER_MODEL_NAME


def test_global_setting_overrides_default_after_save():
    save_global_settings(GlobalSettings(reviewer_model_name="claude-sonnet-4-6"))
    assert load_global_settings().reviewer_model_name == "claude-sonnet-4-6"


def test_project_override_takes_priority_over_global():
    save_global_settings(GlobalSettings(reviewer_model_name="claude-sonnet-4-6"))
    project_settings = load_project_settings("alpha")
    project_settings.reviewer_model_name_override = "claude-opus-4-7"
    save_project_settings(project_settings)
    assert resolve_reviewer_model_name_for_project("alpha") == "claude-opus-4-7"


def test_global_used_when_no_project_override():
    save_global_settings(GlobalSettings(reviewer_model_name="claude-sonnet-4-6"))
    project_settings = load_project_settings("alpha-no-override")
    save_project_settings(project_settings)
    assert resolve_reviewer_model_name_for_project("alpha-no-override") == "claude-sonnet-4-6"


def test_default_model_used_when_neither_global_file_nor_project_override():
    if config_module.GLOBAL_SETTINGS_FILE_PATH.exists():
        config_module.GLOBAL_SETTINGS_FILE_PATH.unlink()
    assert resolve_reviewer_model_name_for_project("any-project") == DEFAULT_REVIEWER_MODEL_NAME


def test_write_default_global_settings_creates_file_with_haiku():
    if config_module.GLOBAL_SETTINGS_FILE_PATH.exists():
        config_module.GLOBAL_SETTINGS_FILE_PATH.unlink()
    write_default_global_settings_if_absent()
    payload = json.loads(config_module.GLOBAL_SETTINGS_FILE_PATH.read_text())
    assert payload["reviewer_model_name"] == DEFAULT_REVIEWER_MODEL_NAME


def test_write_default_global_settings_does_not_overwrite_existing():
    save_global_settings(GlobalSettings(reviewer_model_name="claude-sonnet-4-6"))
    write_default_global_settings_if_absent()
    assert load_global_settings().reviewer_model_name == "claude-sonnet-4-6"
