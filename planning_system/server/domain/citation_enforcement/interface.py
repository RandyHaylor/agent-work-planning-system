"""CitationEnforcement: the one public interface of citation_enforcement, the deterministic gate every
content write and node title passes before anything is stored. Pure checking over ReferenceLibrary."""
from abc import ABC, abstractmethod
from typing import Iterable

from .types import CheckedClaim


class CitationEnforcement(ABC):
    @abstractmethod
    def check_content(self, text: str, tags: Iterable[str]) -> CheckedClaim:
        """Raises planning_system.contract.Invalid telling the writer exactly what to fix."""

    @abstractmethod
    def check_title(self, title: str) -> None:
        """Raises Invalid for an empty, long, cited or sentence-shaped title."""
