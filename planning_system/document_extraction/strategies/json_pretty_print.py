"""validates JSON -> json"""
from __future__ import annotations

import json

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyFailed, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy


class JsonPrettyPrint(ExtractionStrategy):
    name = "json_pretty_print"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        text = source.decoded_text().lstrip("﻿")
        try:
            json.loads(text)
        except ValueError as error:
            raise StrategyFailed(f"invalid JSON: {error}") from error
        return StrategyOutput(text, "json")  # the normalizer pretty-prints
