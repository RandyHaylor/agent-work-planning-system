"""citing_and_rendering: pointer validation, server-rendered quoted text, superseded-by chain."""


class CitingAndRendering:
    def __init__(self, storage):
        self._storage = storage

    def get(self, ref_id, follow_superseded=True):
        raise NotImplementedError

    def read_lines(self, ref_id, start, end):
        raise NotImplementedError

    def validate(self, citation):
        """Raises Invalid when the line range is outside the item."""
        raise NotImplementedError

    def render(self, citation):
        raise NotImplementedError

    def supersede(self, old_id, new_id):
        raise NotImplementedError
