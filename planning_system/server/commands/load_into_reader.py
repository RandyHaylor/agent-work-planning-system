"""POST /reader/load: fetch / upload / web search -> document_extraction -> the caller's temp cache.
Exactly one source: url, file_name + file_base64, or search_terms."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Invalid, Principal
from planning_system.server.domain.references import (SourceRequest, UploadRequest, UrlRequest,
                                                      WebSearchRequest)

from .command import WriteCommand
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

    def source_request(self) -> SourceRequest:
        if self.url is not None:
            return UrlRequest(self.url)
        if self.search_terms is not None:
            return WebSearchRequest(self.search_terms)
        try:
            data = base64.b64decode(self.file_base64, validate=True)
        except (binascii.Error, ValueError):
            raise Invalid("file_base64 is not valid base64") from None
        return UploadRequest(self.file_name, data)

    def required_permission(self) -> Permission:
        return Authenticated()

    def run(self, services, principal: Optional[Principal]) -> Any:
        loaded = services.reader.load(principal, self.source_request(), self.strategy, self.line_start,
                                      self.line_count)
        return [{**item, "related_references": self._related(services, item)} for item in loaded]

    @staticmethod
    def _related(services, item: dict) -> dict:
        """Supersede spec "Search first": stored references from the same source and the top same-topic ones."""
        text = services.temp_cache.get(item["cache_id"]).text
        found = services.related.related((item.get("metadata") or {}).get("locator"), text,
                                         exclude_id=item["cache_id"])
        return {"same_source": list(found.same_source), "same_topic": list(found.same_topic)}
