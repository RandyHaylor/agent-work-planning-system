from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Iterator

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyFailed, StrategyOutput


class ExtractionStrategy(ABC):
    """One extractor. Raises StrategyFailed on library error, empty output or unreadable input."""
    name: str

    @abstractmethod
    def extract(self, source: ExtractionInput) -> StrategyOutput: ...


@contextmanager
def library_errors() -> Iterator[None]:
    """Any exception from a third-party library becomes StrategyFailed with its message."""
    try:
        yield
    except StrategyFailed:
        raise
    except Exception as error:  # noqa: BLE001 - libraries raise anything; the runner records it
        raise StrategyFailed(f"{type(error).__name__}: {error}") from error
