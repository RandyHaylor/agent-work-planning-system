from __future__ import annotations

from planning_system.quick_json_reader.json_line_locator.json_source_map import JsonSourceMap, JsonSourceMapLibrary
from planning_system.quick_json_reader.json_line_locator.jsonl_locator import JsonlLocator
from planning_system.quick_json_reader.json_line_locator.pretty_json_locator import PrettyJsonLocator
from planning_system.quick_json_reader.json_reader_interface import JsonLineLocator, JsonLineLocatorFactory
from planning_system.quick_json_reader.json_reader_types import TextKind


class StoredTextLocatorFactory(JsonLineLocatorFactory):
    def __init__(self, source_map: JsonSourceMap | None = None) -> None:
        self.source_map = source_map or JsonSourceMapLibrary()

    def for_text(self, stored_text: str, text_kind: TextKind) -> JsonLineLocator:
        if text_kind == "jsonl":
            return JsonlLocator(stored_text)
        return PrettyJsonLocator(stored_text, self.source_map)
