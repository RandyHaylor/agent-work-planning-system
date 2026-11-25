"""Port: any source the reader loads (URL, uploaded file, web search) -> SourceDocument.

Spec 05-spec-source-fetching.md. Adapters live in planning_system/server/adapters/. Fetchers never
extract, store or cache.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Union

from planning_system.document_extraction.extraction_types import SourceDocument


@dataclass(frozen=True)
class UrlRequest:
    url: str


@dataclass(frozen=True)
class UploadRequest:
    file_name: str
    file_bytes: bytes


@dataclass(frozen=True)
class WebSearchRequest:
    terms: str
    limit: int = 10


SourceRequest = Union[UrlRequest, UploadRequest, WebSearchRequest]


class FetchFailed(Exception):
    """reason: "http 404", "cloudflare challenge (cf-mitigated)", "empty body", "timeout", "too large"."""

    def __init__(self, locator: str, reason: str, status: int | None = None) -> None:
        self.locator, self.reason, self.status = locator, reason, status
        super().__init__(f"{locator}: {reason}")


class SourceFetcher(ABC):
    @abstractmethod
    def fetch(self, request: SourceRequest) -> SourceDocument:
        """Raises FetchFailed."""


__all__ = ["UrlRequest", "UploadRequest", "WebSearchRequest", "SourceRequest", "FetchFailed", "SourceFetcher",
           "SourceDocument"]
