"""JSONL stored one record per line: first step n -> line n+1; deeper steps -> the same line."""
from __future__ import annotations

from typing import Sequence

from planning_system.quick_json_reader.json_reader_interface import JsonLineLocator
from planning_system.quick_json_reader.json_reader_types import LineRange


class JsonlLocator(JsonLineLocator):
    def __init__(self, stored_text: str) -> None:
        self.stored_text = stored_text

    def locate(self, address_steps: Sequence[int]) -> LineRange:
        raise NotImplementedError("level 7")
