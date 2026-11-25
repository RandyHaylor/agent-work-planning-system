"""Builds the per-turn / per-subagent context injection text for the primary agent."""
from __future__ import annotations

from .compact_tree_renderer import render_tree_titles_only_indented
from .load_config import resolve_effective_global_settings
from .requirements_tree_store import load_requirements_tree


def build_top_level_injection_text_for_project(project_id: str) -> str:
    tree = load_requirements_tree(project_id)
    tree_compact_text = render_tree_titles_only_indented(project_id, tree)
    # Project override of the template if set, else the global default.
    template = resolve_effective_global_settings(project_id).top_level_injection_blurb_template
    return template.format(tree_compact_text=tree_compact_text)
