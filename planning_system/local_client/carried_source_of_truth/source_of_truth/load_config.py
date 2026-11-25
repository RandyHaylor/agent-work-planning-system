"""Loads global + per-project settings and exposes the system-wide constants and paths."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SOURCE_OF_TRUTH_ROOT_DIR: Path = Path.home() / ".source-of-truth"
GLOBAL_SETTINGS_FILE_PATH: Path = SOURCE_OF_TRUTH_ROOT_DIR / "global-settings.json"
PROJECTS_PARENT_DIR: Path = SOURCE_OF_TRUTH_ROOT_DIR / "projects"

# The tunable global-setting VALUES (char limits + the agent-guidance text
# templates) intentionally do NOT live in this module. They live in JSON:
#   * shipped defaults: default-global-settings.json (next to this module)
#   * live overrides:   ~/.source-of-truth/global-settings.json
# This module is now a pure loader. The historical constant NAMES
# (PRE_SUBMISSION_CAPTURE_CHAR_LIMIT, CHAR_RANGE_ALLOWED_ABOVE_THRESHOLD,
# MIN_CHAR_RANGE_LENGTH, INTERACTION_TIME_AGENT_GUIDANCE,
# TOP_LEVEL_INJECTION_BLURB_TEMPLATE) are re-exported at the BOTTOM of this
# file, sourced from the loaded settings, so existing importers keep working.
#
# char_range is FORBIDDEN when submission length <= threshold (whole entry is
# the citation), and ALLOWED-BUT-OPTIONAL when submission length > threshold.
PACKAGE_DEFAULT_GLOBAL_SETTINGS_FILE_PATH: Path = (
    Path(__file__).parent / "default-global-settings.json"
)

# Last-resort fallbacks, used ONLY if a key is absent from BOTH JSON files.
# The shipped default file carries every key, so these should never be hit in a
# real install; they exist purely so the loader cannot crash on a broken setup.
_FALLBACK_CHAR_RANGE_ALLOWED_ABOVE_THRESHOLD: int = 500
_FALLBACK_PRE_SUBMISSION_CAPTURE_CHAR_LIMIT: int = 2000
_FALLBACK_MIN_CHAR_RANGE_LENGTH: int = 1
_FALLBACK_INTERACTION_TIME_AGENT_GUIDANCE: str = ""
_FALLBACK_TOP_LEVEL_INJECTION_BLURB_TEMPLATE: str = ""


DEFAULT_REVIEWER_MODEL_NAME: str = "claude-haiku-4-5-20251001"

REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT: str = "live"
REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY: str = "none"
REVIEWER_MODE_DEFER_UNTIL_FLUSH: str = "deferred"

ALL_VALID_REVIEWER_MODES: tuple[str, ...] = (
    REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    REVIEWER_MODE_DEFER_UNTIL_FLUSH,
)

DEFAULT_REVIEWER_MODE: str = REVIEWER_MODE_LIVE_REVIEW_EVERY_SUBMIT

# When ON (the new default), the live-review submit path NEVER rejects and NEVER
# blocks: every op is applied immediately, and a DETACHED background process
# generalizes only the node TITLES (stripping specific requirement detail),
# reporting any changes via the existing pending-message queue. When OFF, the
# legacy synchronous per-op review (which can reject and amend titles inline)
# runs instead. Kept as an internal, reversible toggle so the legacy path stays
# available (and is exercised by tests that pin this False).
REVIEWER_TITLE_ONLY_NONBLOCKING: bool = True


# Every global setting a project may override, keyed by its EXACT global key
# name (the same key used in global-settings.json). resolve_effective_global_
# settings() applies a project's overrides for any of these.
OVERRIDABLE_GLOBAL_SETTING_NAMES: tuple[str, ...] = (
    "reviewer_command",
    "reviewer_model_name",
    "reviewer_mode",
    "pre_submission_capture_char_limit",
    "char_range_allowed_above_threshold",
    "min_char_range_length",
    "interaction_time_agent_guidance",
    "top_level_injection_blurb_template",
)

# JSON has no native comments, so a freshly created project-settings.json carries
# this underscore-prefixed "comment" key (ignored by the loader, preserved on
# save) documenting how to override each global setting. Seeded ONLY at project
# creation; existing projects are left untouched.
PROJECT_SETTINGS_OVERRIDE_COMMENT_KEY: str = "_comment_overrides"
PROJECT_SETTINGS_OVERRIDE_COMMENT_TEXT: str = (
    "To override a GLOBAL setting for THIS project only, add the setting's exact "
    "key under the 'overrides' object (leave 'overrides' empty to inherit "
    "everything). Recognized keys: "
    + ", ".join(OVERRIDABLE_GLOBAL_SETTING_NAMES)
    + '. Example -> "overrides": {"reviewer_mode": "none", '
    '"pre_submission_capture_char_limit": 4000}. Anything not overridden '
    "inherits the global value from ~/.source-of-truth/global-settings.json."
)


@dataclass
class GlobalSettings:
    reviewer_command: list[str] = field(default_factory=lambda: ["claude", "-p"])
    reviewer_model_name: str = DEFAULT_REVIEWER_MODEL_NAME
    reviewer_mode: str = DEFAULT_REVIEWER_MODE
    pre_submission_capture_char_limit: int = _FALLBACK_PRE_SUBMISSION_CAPTURE_CHAR_LIMIT
    char_range_allowed_above_threshold: int = _FALLBACK_CHAR_RANGE_ALLOWED_ABOVE_THRESHOLD
    min_char_range_length: int = _FALLBACK_MIN_CHAR_RANGE_LENGTH
    interaction_time_agent_guidance: str = _FALLBACK_INTERACTION_TIME_AGENT_GUIDANCE
    top_level_injection_blurb_template: str = _FALLBACK_TOP_LEVEL_INJECTION_BLURB_TEMPLATE
    raw_extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectSettings:
    project_id: str
    member_sessions: list[dict[str, str]] = field(default_factory=list)
    historical_reviewer_session_ids: list[str] = field(default_factory=list)
    current_reviewer_session_id: str | None = None
    reviewer_model_name_override: str | None = None
    reviewer_mode_override: str | None = None
    overrides: dict[str, Any] = field(default_factory=dict)
    raw_extra: dict[str, Any] = field(default_factory=dict)


def project_directory_for(project_id: str) -> Path:
    return PROJECTS_PARENT_DIR / project_id


def project_settings_file_path(project_id: str) -> Path:
    return project_directory_for(project_id) / "project-settings.json"


def project_source_of_truth_file_path(project_id: str) -> Path:
    return project_directory_for(project_id) / f"project-{project_id}-source-of-truth.json"


def project_raw_input_log_file_path(project_id: str) -> Path:
    return project_directory_for(project_id) / "raw_input_log.json"


def project_reviewer_thinking_log_file_path(project_id: str) -> Path:
    return project_directory_for(project_id) / "reviewer_thinking.log"


def project_deferred_change_sets_queue_file_path(project_id: str) -> Path:
    return project_directory_for(project_id) / "deferred_change_sets_queue.jsonl"


def ensure_root_directories_exist() -> None:
    SOURCE_OF_TRUTH_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_PARENT_DIR.mkdir(parents=True, exist_ok=True)


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_global_settings() -> GlobalSettings:
    # Shipped defaults first, then overlay the live user file (live wins per key).
    merged: dict[str, Any] = _read_json_dict(PACKAGE_DEFAULT_GLOBAL_SETTINGS_FILE_PATH)
    merged.update(_read_json_dict(GLOBAL_SETTINGS_FILE_PATH))
    known_keys = {
        "reviewer_command", "reviewer_model_name", "reviewer_mode",
        "pre_submission_capture_char_limit", "char_range_allowed_above_threshold",
        "min_char_range_length", "interaction_time_agent_guidance",
        "top_level_injection_blurb_template",
    }
    return GlobalSettings(
        reviewer_command=merged.get("reviewer_command", ["claude", "-p"]),
        reviewer_model_name=merged.get("reviewer_model_name", DEFAULT_REVIEWER_MODEL_NAME),
        reviewer_mode=merged.get("reviewer_mode", DEFAULT_REVIEWER_MODE),
        pre_submission_capture_char_limit=merged.get(
            "pre_submission_capture_char_limit", _FALLBACK_PRE_SUBMISSION_CAPTURE_CHAR_LIMIT),
        char_range_allowed_above_threshold=merged.get(
            "char_range_allowed_above_threshold", _FALLBACK_CHAR_RANGE_ALLOWED_ABOVE_THRESHOLD),
        min_char_range_length=merged.get(
            "min_char_range_length", _FALLBACK_MIN_CHAR_RANGE_LENGTH),
        interaction_time_agent_guidance=merged.get(
            "interaction_time_agent_guidance", _FALLBACK_INTERACTION_TIME_AGENT_GUIDANCE),
        top_level_injection_blurb_template=merged.get(
            "top_level_injection_blurb_template", _FALLBACK_TOP_LEVEL_INJECTION_BLURB_TEMPLATE),
        raw_extra={k: v for k, v in merged.items() if k not in known_keys},
    )


def save_global_settings(settings: GlobalSettings) -> None:
    SOURCE_OF_TRUTH_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "reviewer_command": settings.reviewer_command,
        "reviewer_model_name": settings.reviewer_model_name,
        "reviewer_mode": settings.reviewer_mode,
        "pre_submission_capture_char_limit": settings.pre_submission_capture_char_limit,
        "char_range_allowed_above_threshold": settings.char_range_allowed_above_threshold,
        "min_char_range_length": settings.min_char_range_length,
        "interaction_time_agent_guidance": settings.interaction_time_agent_guidance,
        "top_level_injection_blurb_template": settings.top_level_injection_blurb_template,
        **settings.raw_extra,
    }
    GLOBAL_SETTINGS_FILE_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True)
    )


def write_default_global_settings_if_absent() -> None:
    if GLOBAL_SETTINGS_FILE_PATH.exists():
        return
    SOURCE_OF_TRUTH_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    # Seed from the shipped default file so the live file gets the REAL defaults
    # (including the long guidance text), not the empty-string fallbacks.
    defaults = _read_json_dict(PACKAGE_DEFAULT_GLOBAL_SETTINGS_FILE_PATH)
    GLOBAL_SETTINGS_FILE_PATH.write_text(json.dumps(defaults, indent=2, sort_keys=True))


def resolve_effective_global_settings(project_id: str) -> GlobalSettings:
    """Return the global settings with THIS project's overrides applied.

    Precedence (highest first):
      1. dedicated reviewer override fields (reviewer_mode_override /
         reviewer_model_name_override, set via `set-mode` etc.),
      2. the generic project `overrides` map (keyed by exact global setting name),
      3. the global default (default-global-settings.json overlaid by the live
         global-settings.json).
    Only recognized global keys are honored; unknown keys in `overrides` are
    ignored. Returns a fresh GlobalSettings; never mutates the global file.
    """
    effective = load_global_settings()
    project_settings = load_project_settings(project_id)

    to_apply: dict[str, Any] = {}
    for key, value in (project_settings.overrides or {}).items():
        if key in OVERRIDABLE_GLOBAL_SETTING_NAMES:
            to_apply[key] = value
    # Dedicated reviewer override fields win over the generic map.
    if project_settings.reviewer_mode_override is not None:
        to_apply["reviewer_mode"] = project_settings.reviewer_mode_override
    if project_settings.reviewer_model_name_override is not None:
        to_apply["reviewer_model_name"] = project_settings.reviewer_model_name_override

    for key, value in to_apply.items():
        setattr(effective, key, value)
    return effective


def resolve_reviewer_model_name_for_project(project_id: str) -> str:
    return resolve_effective_global_settings(project_id).reviewer_model_name


def resolve_reviewer_mode_for_project(project_id: str) -> str:
    return resolve_effective_global_settings(project_id).reviewer_mode


def load_project_settings(project_id: str) -> ProjectSettings:
    settings_file = project_settings_file_path(project_id)
    if not settings_file.exists():
        return ProjectSettings(project_id=project_id)
    raw = json.loads(settings_file.read_text())
    return ProjectSettings(
        project_id=project_id,
        member_sessions=raw.get("member_sessions", []),
        historical_reviewer_session_ids=raw.get("historical_reviewer_session_ids", []),
        current_reviewer_session_id=raw.get("current_reviewer_session_id"),
        reviewer_model_name_override=raw.get("reviewer_model_name_override"),
        reviewer_mode_override=raw.get("reviewer_mode_override"),
        overrides=raw.get("overrides", {}),
        raw_extra={k: v for k, v in raw.items() if k not in {
            "member_sessions", "historical_reviewer_session_ids",
            "current_reviewer_session_id", "reviewer_model_name_override",
            "reviewer_mode_override", "overrides",
        }},
    )


def save_project_settings(settings: ProjectSettings) -> None:
    """Write project-settings.json atomically under a cross-platform file lock.

    Two safeguards:
      1. Cross-platform file lock around the write so concurrent writers
         (multiple registered sessions adding themselves at once, etc.)
         do not interleave their payload bytes.
      2. Temp-file-and-rename so any concurrent reader always sees either
         the previous complete file or the new complete file -- never a
         partially-written one.
    """
    import os
    import tempfile
    from .cross_platform_file_lock import acquire_exclusive_file_lock

    project_directory_for(settings.project_id).mkdir(parents=True, exist_ok=True)
    settings_file = project_settings_file_path(settings.project_id)
    payload: dict[str, Any] = {
        "member_sessions": settings.member_sessions,
        "historical_reviewer_session_ids": settings.historical_reviewer_session_ids,
        "current_reviewer_session_id": settings.current_reviewer_session_id,
        "overrides": settings.overrides,
        **settings.raw_extra,
    }
    if settings.reviewer_model_name_override is not None:
        payload["reviewer_model_name_override"] = settings.reviewer_model_name_override
    if settings.reviewer_mode_override is not None:
        payload["reviewer_mode_override"] = settings.reviewer_mode_override
    payload_text = json.dumps(payload, indent=2, sort_keys=True)
    with acquire_exclusive_file_lock(settings_file):
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=".sot-settings-", suffix=".tmp", dir=str(settings_file.parent)
        )
        try:
            with os.fdopen(temp_fd, "w") as temp_file_handle:
                temp_file_handle.write(payload_text)
            os.replace(temp_path_str, settings_file)
        except Exception:
            try:
                os.unlink(temp_path_str)
            except OSError:
                pass
            raise


# ---------------------------------------------------------------------------
# Back-compat re-exports. These names used to be literal constants in this
# module; their VALUES now live in JSON (default-global-settings.json overlaid
# by ~/.source-of-truth/global-settings.json) and are loaded once at import
# time. Existing importers (e.g. `from .load_config import
# PRE_SUBMISSION_CAPTURE_CHAR_LIMIT`) keep working unchanged.
# ---------------------------------------------------------------------------
_GLOBAL_SETTINGS_AT_IMPORT: GlobalSettings = load_global_settings()
PRE_SUBMISSION_CAPTURE_CHAR_LIMIT: int = _GLOBAL_SETTINGS_AT_IMPORT.pre_submission_capture_char_limit
CHAR_RANGE_ALLOWED_ABOVE_THRESHOLD: int = _GLOBAL_SETTINGS_AT_IMPORT.char_range_allowed_above_threshold
MIN_CHAR_RANGE_LENGTH: int = _GLOBAL_SETTINGS_AT_IMPORT.min_char_range_length
INTERACTION_TIME_AGENT_GUIDANCE: str = _GLOBAL_SETTINGS_AT_IMPORT.interaction_time_agent_guidance
TOP_LEVEL_INJECTION_BLURB_TEMPLATE: str = _GLOBAL_SETTINGS_AT_IMPORT.top_level_injection_blurb_template
