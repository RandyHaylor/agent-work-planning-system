from __future__ import annotations

from .json_source_map import JsonSourceMap, JsonSourceMapLibrary
from .jsonl_locator import JsonlLocator
from .pretty_json_locator import PrettyJsonLocator
from ..json_reader_interface import JsonLineLocator, JsonLineLocatorFactory
from ..json_reader_types import TextKind


class StoredTextLocatorFactory(JsonLineLocatorFactory):
    def __init__(self, source_map: JsonSourceMap | None = None) -> None:
        self.source_map = source_map or JsonSourceMapLibrary()

    def for_text(self, stored_text: str, text_kind: TextKind) -> JsonLineLocator:
        if text_kind == "jsonl":
            return JsonlLocator(stored_text)
        return PrettyJsonLocator(stored_text, self.source_map)
