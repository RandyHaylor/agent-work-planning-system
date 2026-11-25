"""JSON pointer -> line positions. Behind an interface because the library (json-source-map on PyPI) is
not a dependency yet: package and license to confirm at level 7."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from planning_system.quick_json_reader.json_reader_types import LineRange


class JsonSourceMap(ABC):
    @abstractmethod
    def pointer_ranges(self, stored_text: str) -> Mapping[str, LineRange]:
        """JSON pointer ("" for the root, "/items/1") -> 1-based start..end line of that value."""


class JsonSourceMapLibrary(JsonSourceMap):
    """Adapter over the json-source-map package (not yet added)."""

    def pointer_ranges(self, stored_text: str) -> Mapping[str, LineRange]:
        raise NotImplementedError("level 7")
