"""GET /references/{id}/lines: ReferenceLibrary.read_lines (whole item when no range).
On a superseded id the answer also carries the current version: the same lines mapped into it (difflib), whether
they changed, and a note (user 2026-11-27)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.domain.references import map_line_range
from planning_system.server.domain.references import numbered

from .command import ReadCommand
from .get_reference import superseded_note
from .permissions import CanReadReference, Permission


@dataclass(frozen=True)
class ReadReferenceLines(ReadCommand):
    reference_id: str
    start: Optional[int] = None
    end: Optional[int] = None

    def required_permission(self) -> Permission:
        return CanReadReference(self.reference_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        """{id, start, end, text}; text is the lines as `N<tab>line` (the reader's lines format). When superseded,
        plus superseded_note and current: {id, start, end, text, unchanged} (start/end/text None if deleted)."""
        requested = services.references.get(self.reference_id, follow_superseded=False)
        start = 1 if self.start is None else self.start
        end = len(requested.text.splitlines()) if self.end is None else self.end
        text = services.references.read_lines(self.reference_id, start, end)
        result = {"id": self.reference_id, "start": start, "end": end, "text": numbered(text.splitlines(), start)}
        current = services.references.get(self.reference_id, follow_superseded=True)
        if current.id != self.reference_id:
            result["superseded_note"] = superseded_note(self.reference_id, current.id)
            result["current"] = self._current_lines(services, requested.text, current, start, end)
        return result

    @staticmethod
    def _current_lines(services, old_text, current, start, end) -> dict:
        mapped = map_line_range(old_text, current.text, start, end)
        text = None
        if mapped.start is not None:
            lines = services.references.read_lines(current.id, mapped.start, mapped.end).splitlines()
            text = numbered(lines, mapped.start)
        return {"id": current.id, "start": mapped.start, "end": mapped.end, "text": text,
                "unchanged": mapped.unchanged}
