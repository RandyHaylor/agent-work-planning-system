"""GET /references/{id}/lines: ReferenceLibrary.read_lines (whole item when no range)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.domain.references.reader_service import numbered

from .command import ReadCommand
from .permissions import CanReadReference, Permission


@dataclass(frozen=True)
class ReadReferenceLines(ReadCommand):
    reference_id: str
    start: Optional[int] = None
    end: Optional[int] = None

    def required_permission(self) -> Permission:
        return CanReadReference(self.reference_id)

    def run(self, services, principal: Optional[Principal]) -> Any:
        """{id, start, end, text}; text is the lines as `N<tab>line` (the reader's lines format)."""
        if self.start is None or self.end is None:
            line_count = len(services.references.get(self.reference_id, follow_superseded=False).text.splitlines())
        start = 1 if self.start is None else self.start
        end = line_count if self.end is None else self.end
        text = services.references.read_lines(self.reference_id, start, end)
        return {"id": self.reference_id, "start": start, "end": end,
                "text": numbered(text.splitlines(), start)}
