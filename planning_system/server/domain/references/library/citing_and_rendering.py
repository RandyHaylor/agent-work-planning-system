"""citing_and_rendering: pointer validation, server-rendered quoted text, superseded-by chain."""
import dataclasses

from planning_system.errors import Invalid, NotFound

from ..citation_syntax import slice_lines
from ..ports import ReferenceStoragePort
from ..types import Citation, Reference


class CitingAndRendering:
    def __init__(self, storage: ReferenceStoragePort):
        self._storage = storage

    def get(self, ref_id, follow_superseded=True) -> Reference:
        ref = self._get_exact(ref_id)
        seen = {ref.id}
        while follow_superseded and ref.superseded_by is not None:
            ref = self._get_exact(ref.superseded_by)
            if ref.id in seen:
                raise Invalid(f"superseded-by cycle at {ref.id}")
            seen.add(ref.id)
        return ref

    def read_lines(self, ref_id, start, end) -> str:
        return slice_lines(self._get_exact(ref_id).text, start, end)

    def validate(self, citation: Citation) -> None:
        """Raises Invalid when the line range is outside the item."""
        self.render(citation)

    def render(self, citation: Citation) -> str:
        return self.read_lines(citation.reference_id, citation.start_line, citation.end_line)

    def supersede(self, old_id, new_id) -> None:
        if old_id == new_id:
            return
        old = self._get_exact(old_id)
        self._get_exact(new_id)
        self._storage.save(dataclasses.replace(old, superseded_by=new_id))

    def _get_exact(self, ref_id) -> Reference:
        ref = self._storage.get(ref_id)
        if ref is None:
            raise NotFound(ref_id)
        return ref
