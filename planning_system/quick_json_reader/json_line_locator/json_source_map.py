"""JSON pointer -> line positions, behind an interface; the adapter uses json-source-map (Apache-2.0,
build log #31). A value's range starts at its key's line, so a cut of the stored lines is the member."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from ..json_reader_types import LineRange


class JsonSourceMap(ABC):
    @abstractmethod
    def pointer_ranges(self, stored_text: str) -> Mapping[str, LineRange]:
        """JSON pointer ("" for the root, "/items/1") -> 1-based start..end line of that value."""


class JsonSourceMapLibrary(JsonSourceMap):
    """Adapter over the json-source-map package (not yet added)."""

    def pointer_ranges(self, stored_text: str) -> Mapping[str, LineRange]:
        import json_source_map

        try:
            entries = json_source_map.calculate(stored_text)
        except Exception as error:  # noqa: BLE001 - the library raises its own error types
            raise ValueError(f"not JSON: {error}") from error
        return {pointer: LineRange((entry.key_start or entry.value_start).line + 1, entry.value_end.line + 1)
                for pointer, entry in entries.items()}
