"""JSON stored in json_formatter's fixed form: ordinal steps -> JSON pointer -> line range."""
from __future__ import annotations

import json
from functools import cached_property
from typing import Mapping, Sequence

from planning_system.quick_json_reader.json_line_locator.json_source_map import JsonSourceMap
from planning_system.quick_json_reader.json_reader_interface import JsonLineLocator
from planning_system.quick_json_reader.json_reader_types import LineRange


class PrettyJsonLocator(JsonLineLocator):
    def __init__(self, stored_text: str, source_map: JsonSourceMap) -> None:
        self.stored_text = stored_text
        self.source_map = source_map

    def locate(self, address_steps: Sequence[int]) -> LineRange:
        return self._ranges[self._pointer(address_steps)]

    def _pointer(self, address_steps: Sequence[int]) -> str:
        """Ordinal steps (n-th member or element) -> JSON pointer; KeyError when a step does not exist."""
        value, parts = self._value, []
        for step in address_steps:
            if isinstance(value, dict) and 0 <= step < len(value):
                key = list(value)[step]
                parts.append(key.replace("~", "~0").replace("/", "~1"))
                value = value[key]
            elif isinstance(value, list) and 0 <= step < len(value):
                parts.append(str(step))
                value = value[step]
            else:
                raise KeyError(tuple(address_steps))
        return "".join("/" + part for part in parts)

    @cached_property
    def _value(self):
        return json.loads(self.stored_text)

    @cached_property
    def _ranges(self) -> Mapping[str, LineRange]:
        return self.source_map.pointer_ranges(self.stored_text)
