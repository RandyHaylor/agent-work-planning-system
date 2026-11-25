"""level_placement_rules: levels 1-4 linear, branching from 5; supplementary tasks exempt at any level."""
from planning_system.contract import Invalid

from .types import ABANDONED, LINEAR_LEVELS, SUPPLEMENTARY_LABELS


def _is_supplementary(labels):
    return bool(frozenset(labels) & SUPPLEMENTARY_LABELS)


def _is_main_child(node):
    """A child that holds the parent's one main slot (abandoned ones give it up)."""
    return not _is_supplementary(node.labels) and node.state != ABANDONED


class LevelPlacementRules:
    def check(self, parent_depth, existing_children, labels):
        """Raises Invalid when a second main child would go under a node at levels 1-3.

        parent_depth: 1 for a project node. existing_children: the parent's current children.
        """
        child_level = parent_depth + 1
        if child_level > LINEAR_LEVELS or _is_supplementary(labels):
            return
        if any(_is_main_child(c) for c in existing_children):
            raise Invalid(f"level {child_level} takes one main child; branching starts at level "
                          f"{LINEAR_LEVELS + 1}")
