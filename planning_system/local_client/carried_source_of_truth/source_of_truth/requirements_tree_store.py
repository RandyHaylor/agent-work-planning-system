"""Atomic load/save of project-<project_id>-source-of-truth.json under file lock.

This module is the SOLE WRITER of the requirements tree on disk. AI agents must
never write to this file directly; they submit change-sets via the controlled API,
which calls this store after reviewer approval.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .load_config import project_directory_for, project_source_of_truth_file_path
from .cross_platform_file_lock import acquire_exclusive_file_lock
from .requirements_tree_node_schema import RequirementsTree


def load_requirements_tree(project_id: str) -> RequirementsTree:
    tree_file_path = project_source_of_truth_file_path(project_id)
    if not tree_file_path.exists():
        return RequirementsTree.empty_for_project(project_id)
    raw = json.loads(tree_file_path.read_text())
    return RequirementsTree.from_json_dict(raw)


def save_requirements_tree_atomically(tree: RequirementsTree) -> None:
    project_directory_for(tree.project_id).mkdir(parents=True, exist_ok=True)
    tree_file_path = project_source_of_truth_file_path(tree.project_id)
    payload_text = json.dumps(tree.to_json_dict(), indent=2, sort_keys=True)
    with acquire_exclusive_file_lock(tree_file_path):
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=".sot-tree-", suffix=".tmp", dir=str(tree_file_path.parent)
        )
        try:
            with os.fdopen(temp_fd, "w") as temp_file_handle:
                temp_file_handle.write(payload_text)
            os.replace(temp_path_str, tree_file_path)
        except Exception:
            try:
                os.unlink(temp_path_str)
            except OSError:
                pass
            raise
