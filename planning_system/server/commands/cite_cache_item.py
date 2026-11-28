"""POST /reader/cite: TempCache.cite (temp cache -> references, keeps the id). When that makes a NEW document
reference from a source (URL or file) already stored with other content, each current older copy gets a
supersede candidate (05-spec-reference-supersede.md 2); nothing is superseded here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import NotFound, Principal

from .command import WriteCommand
from .permissions import CanReadReaderItems, Permission
from .supersede_flow import same_source_candidates


@dataclass(frozen=True)
class CiteCacheItem(WriteCommand):
    reader_id: str
    start_line: int
    end_line: int

    def required_permission(self) -> Permission:
        return CanReadReaderItems((self.reader_id,))

    def run(self, services, principal: Optional[Principal]) -> Any:
        is_new = self._is_temp_item(services)
        citation = services.reader.cite(principal, self.reader_id, self.start_line, self.end_line)
        if is_new and citation.reference_id == self.reader_id:
            same_source_candidates(services, principal, citation.reference_id)
        return citation

    def _is_temp_item(self, services) -> bool:
        try:
            services.temp_cache.get(self.reader_id)
        except NotFound:                                     # already a reference
            return False
        return True
