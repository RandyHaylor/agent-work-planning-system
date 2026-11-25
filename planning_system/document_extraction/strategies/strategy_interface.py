from __future__ import annotations

from abc import ABC, abstractmethod

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyOutput


class ExtractionStrategy(ABC):
    """One extractor. Raises StrategyFailed on library error, empty output or unreadable input."""
    name: str

    @abstractmethod
    def extract(self, source: ExtractionInput) -> StrategyOutput: ...
