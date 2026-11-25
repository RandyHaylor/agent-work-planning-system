"""POST /reader/load: fetch / upload / web search -> document_extraction -> the caller's temp cache.
Exactly one source: url, file_name + file_base64, or search_terms."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal

from.command import WriteCommand, hollow
from .permissions import Authenticated, Permission


@dataclass(frozen=True)
class LoadIntoReader(WriteCommand):
    url: Optional[str] = None
    file_name: Optional[str] = None
    file_base64: Optional[str] = None
    search_terms: Optional[str] = None
    strategy: Optional[str] = None
    line_start: Optional[int] = None
    line_count: Optional[int] = None

    def __post_init__(self) -> None:
        sources = [self.url is not None, self.file_name is not None or self.file_base64 is not None,
                   self.search_terms is not None]
        if sum(sources) != 1:
            raise Invalid("give exactly one of url, file_name + file_base64, search_terms")
        if (self.file_name is None) != (self.file_base64 is None):
            raise Invalid("file_name and file_base64 go together")

    def required_permission(self) -> Permission:
        return Authenticated()

    def run(self, services, principal: Optional[Principal]) -> Any:
        return hollow()
