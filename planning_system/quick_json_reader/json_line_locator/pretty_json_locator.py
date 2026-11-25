"""JSON stored in json_formatter's fixed form: ordinal steps -> JSON pointer -> line range."""
from __future__ import annotations

from typing import Sequence

from planning_system.quick_json_reader.json_line_locator.json_source_map import JsonSourceMap
from planning_system.quick_json_reader.json_reader_interface import JsonLineLocator
from planning_system.quick_json_reader.json_reader_types import LineRange


class PrettyJsonLocator(JsonLineLocator):
    def __init__(self, stored_text: str, source_map: JsonSourceMap) -> None:
        self.stored_text = stored_text
        self.source_map = source_map

    def locate(self, address_steps: Sequence[int]) -> LineRange:
        raise NotImplementedError("level 7")
