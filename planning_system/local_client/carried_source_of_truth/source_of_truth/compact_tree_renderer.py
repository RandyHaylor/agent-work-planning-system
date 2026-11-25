"""Compact human/agent-friendly tree rendering with inlined quote text for top levels.

JSON dumps of the requirements tree are bulky and hide the actual requirement text
behind raw_input_id pointers. This renderer walks the tree and emits a compact
indented listing where the top N levels (default 2) inline the resolved quote
text, and deeper levels show only id + kind + child count.
"""
from __future__ import annotations

from .raw_input_log_reader import (
    CharRangeOutOfBoundsError,
    RawLogEntryNotFoundError,
    resolve_quote_text_from_reference,
)
from .id_display import (
    format_node_id_for_display,
    format_raw_input_id_for_display,
)
from .requirements_tree_node_schema import (
    PROJECT_PATHS_SPECIAL_NODE_KIND,
    QUOTE_REFERENCE_NODE_KIND,
    RequirementsTree,
    RequirementsTreeNode,
)


def _shorten_to_one_line(text: str, max_chars: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 1].rstrip() + "..."


def _resolve_quote_text_or_placeholder(project_id: str, node: RequirementsTreeNode) -> str:
    ref = node.raw_input_reference
    if ref is None:
        return "(no raw_input_reference)"
    char_range_tuple = tuple(ref.char_range) if ref.char_range is not None else None
    try:
        return resolve_quote_text_from_reference(
            project_id, ref.raw_input_id, char_range_tuple, ref.pre_text_line_range
        )
    except (RawLogEntryNotFoundError, CharRangeOutOfBoundsError, ValueError) as exc:
        return f"(resolve error: {exc})"


def _render_node_line(
    project_id: str,
    node: RequirementsTreeNode,
    depth: int,
    max_inlined_depth: int,
    max_quote_chars: int,
) -> str:
    indent = "  " * depth
    child_count = len(node.child_node_ids)
    node_id_label = format_node_id_for_display(node.node_id)
    if node.kind == PROJECT_PATHS_SPECIAL_NODE_KIND:
        paths_summary = ", ".join(node.project_paths) if node.project_paths else "(no paths)"
        return f"{indent}[{node_id_label}] project_paths: {paths_summary}"
    if depth < max_inlined_depth and node.kind == QUOTE_REFERENCE_NODE_KIND:
        quote_text = _resolve_quote_text_or_placeholder(project_id, node)
        ref = node.raw_input_reference
        raw_id_label = format_raw_input_id_for_display(ref.raw_input_id) if ref else "raw-?"
        children_label = f" (+{child_count})" if child_count else ""
        return (
            f"{indent}[{node_id_label}] {raw_id_label}{children_label}: "
            f"{_shorten_to_one_line(quote_text, max_quote_chars)}"
        )
    # Groups (and any node past the inlined depth): show the human title if present,
    # falling back to the kind only when there's no title.
    title_or_kind = node.short_neutral_title if node.short_neutral_title else node.kind
    children_label = f" (+{child_count} children)" if child_count else ""
    return f"{indent}[{node_id_label}] {title_or_kind}{children_label}"


def render_tree_titles_only_indented(project_id: str, tree: RequirementsTree) -> str:
    """Compact <id> <short_neutral_title> view, indented for hierarchy. No brackets, no quote text.

    Default for show-tree and per-turn injection. Maximally scannable: each line is
    "<node_id> <title>", indented by depth*2 spaces.
    """
    top_level_node_ids = tree.list_top_level_node_ids()
    output_lines: list[str] = [
        f"project {project_id}: {len(tree.nodes_by_id)} nodes, "
        f"{len(top_level_node_ids)} top-level"
    ]
    if not top_level_node_ids:
        return output_lines[0] + " (empty)"

    def _walk(node_id: str, depth: int) -> None:
        node = tree.nodes_by_id.get(node_id)
        if node is None:
            output_lines.append(
                ("  " * depth) + f"{format_node_id_for_display(node_id)} (missing)"
            )
            return
        title_for_display = (
            node.short_neutral_title
            if node.short_neutral_title
            else f"({node.kind})"
        )
        output_lines.append(
            ("  " * depth)
            + f"{format_node_id_for_display(node.node_id)} {title_for_display}"
        )
        for child_id in node.child_node_ids:
            _walk(child_id, depth + 1)

    for top_id in top_level_node_ids:
        _walk(top_id, 0)
    return "\n".join(output_lines)


def render_tree_compact(
    project_id: str,
    tree: RequirementsTree,
    max_inlined_depth: int = 2,
    max_quote_chars: int = 240,
) -> str:
    """Compact indented listing; top `max_inlined_depth` levels inline quote text."""
    top_level_node_ids = tree.list_top_level_node_ids()
    if not top_level_node_ids:
        return f"(project {project_id}: 0 nodes)"
    output_lines: list[str] = [
        f"project {project_id}: {len(tree.nodes_by_id)} nodes, "
        f"{len(top_level_node_ids)} top-level"
    ]

    def _walk(node_id: str, depth: int) -> None:
        node = tree.nodes_by_id.get(node_id)
        if node is None:
            output_lines.append(
                "  " * depth + f"[{format_node_id_for_display(node_id)}] (missing)"
            )
            return
        output_lines.append(_render_node_line(
            project_id, node, depth, max_inlined_depth, max_quote_chars
        ))
        for child_id in node.child_node_ids:
            _walk(child_id, depth + 1)

    for top_id in top_level_node_ids:
        _walk(top_id, 0)
    return "\n".join(output_lines)
