"""level_placement_rules: levels 1-4 linear, branching from 5; supplementary tasks exempt at any level."""


class LevelPlacementRules:
    def check(self, parent_depth, existing_children, labels):
        """Raises Invalid when a second main child would go under a node at levels 1-3.

        parent_depth: 1 for a project node. existing_children: the parent's current children.
        """
        raise NotImplementedError
