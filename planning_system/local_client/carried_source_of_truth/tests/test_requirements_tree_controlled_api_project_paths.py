from __future__ import annotations

import pytest

from source_of_truth.ai_cli_adapter_interface import (
    AiCliAdapterInterface,
    PersistentReviewerSessionHandle,
)
from source_of_truth.requirements_tree_controlled_api import (
    RequirementsTreeControlledApi,
)
from source_of_truth.requirements_tree_node_schema import (
    PROJECT_PATHS_SPECIAL_NODE_KIND,
)
from source_of_truth.requirements_tree_store import load_requirements_tree


class _StubReviewerHandle(PersistentReviewerSessionHandle):
    @property
    def session_id(self): return "stub"
    def send_prompt_and_await_response(self, prompt_text): return ""
    def is_alive(self): return True
    def terminate(self): pass


class _StubAdapter(AiCliAdapterInterface):
    def get_current_session_id(self): return "stub-sess"
    def register_user_prompt_submit_hook(self, hook_callable): pass
    def inject_into_next_user_turn(self, injection_text): pass
    def inject_into_subagent_spawn(self, injection_text): pass
    def spawn_persistent_reviewer_session(self, **kwargs): return _StubReviewerHandle()


def test_add_project_path_rejects_non_existent_path(tmp_path):
    api = RequirementsTreeControlledApi("proj-x", _StubAdapter())
    with pytest.raises(ValueError):
        api.add_project_path(str(tmp_path / "does_not_exist"))


def test_add_project_path_persists_validated_path_to_special_node(tmp_path):
    api = RequirementsTreeControlledApi("proj-x", _StubAdapter())
    valid_path = tmp_path / "real_dir"
    valid_path.mkdir()
    assert api.add_project_path(str(valid_path)) is True
    tree = load_requirements_tree("proj-x")
    project_paths_nodes = [
        n for n in tree.nodes_by_id.values()
        if n.kind == PROJECT_PATHS_SPECIAL_NODE_KIND
    ]
    assert len(project_paths_nodes) == 1
    assert str(valid_path) in project_paths_nodes[0].project_paths


def test_add_project_path_idempotent_when_already_present(tmp_path):
    api = RequirementsTreeControlledApi("proj-x", _StubAdapter())
    valid_path = tmp_path / "real_dir"
    valid_path.mkdir()
    api.add_project_path(str(valid_path))
    assert api.add_project_path(str(valid_path)) is False
