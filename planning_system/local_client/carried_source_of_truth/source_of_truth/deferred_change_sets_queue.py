"""Per-project queue of change-sets that the agent submitted while in deferred mode.

In deferred mode, submit_requirements_tree_change_set validates references and
appends the change-set here instead of contacting the reviewer. When the agent
calls flush_deferred_change_sets_for_review(), all queued change-sets are merged
and sent to the reviewer in a single round-trip.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .load_config import project_deferred_change_sets_queue_file_path
from .cross_platform_file_lock import acquire_exclusive_file_lock


def append_change_set_to_deferred_queue(
    project_id: str, change_set_json_dict: dict[str, Any]
) -> None:
    file_path = project_deferred_change_sets_queue_file_path(project_id)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    line_payload = json.dumps({
        "queued_at_iso": datetime.now(timezone.utc).isoformat(),
        "change_set": change_set_json_dict,
    })
    with acquire_exclusive_file_lock(file_path):
        with file_path.open("a") as file_handle:
            file_handle.write(line_payload + "\n")


def read_and_clear_all_deferred_change_sets(project_id: str) -> list[dict[str, Any]]:
    file_path = project_deferred_change_sets_queue_file_path(project_id)
    if not file_path.exists():
        return []
    drained: list[dict[str, Any]] = []
    with acquire_exclusive_file_lock(file_path):
        try:
            raw_text = file_path.read_text()
        except OSError:
            return []
        for line in raw_text.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            try:
                drained.append(json.loads(line_stripped))
            except json.JSONDecodeError:
                continue
        file_path.write_text("")
    return drained


def count_pending_deferred_change_sets(project_id: str) -> int:
    file_path = project_deferred_change_sets_queue_file_path(project_id)
    if not file_path.exists():
        return 0
    with acquire_exclusive_file_lock(file_path):
        return sum(1 for line in file_path.read_text().splitlines() if line.strip())
