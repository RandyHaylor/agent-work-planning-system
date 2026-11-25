"""Public interface of document_extraction and of its replaceable parts (ABCs)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from planning_system.document_extraction.extraction_types import ExtractionResult, SourceDocument, TextKind


class DocumentExtractor(ABC):
    """Bytes + metadata in, citable text out."""

    @abstractmethod
    def extract(self, document: SourceDocument, strategy: str | None = None) -> ExtractionResult: ...

    @abstractmethod
    def strategy_names(self, content_type: str | None = None) -> tuple[str, ...]: ...


class ContentTypeDetector(ABC):
    @abstractmethod
    def detect(self, raw_bytes: bytes, content_type_header: str | None, file_name: str | None) -> str: ...


class TextDecoder(ABC):
    @abstractmethod
    def decode(self, raw_bytes: bytes, content_type_header: str | None) -> str: ...


class TextNormalizer(ABC):
    @abstractmethod
    def normalize(self, text: str, kind: TextKind) -> str: ...


class StrategyCatalog(ABC):
    """Name -> strategy, plus the default order per content type."""

    @abstractmethod
    def get(self, name: str): ...  # -> ExtractionStrategy; raises UnknownStrategy

    @abstractmethod
    def default_order(self, content_type: str) -> tuple[str, ...]: ...

    @abstractmethod
    def names(self) -> tuple[str, ...]: ...
