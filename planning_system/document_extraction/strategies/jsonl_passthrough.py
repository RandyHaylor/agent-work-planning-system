"""validates each JSONL record -> jsonl"""
from __future__ import annotations

import json

from planning_system.document_extraction.extraction_types import ExtractionInput, StrategyFailed, StrategyOutput
from planning_system.document_extraction.strategies.strategy_interface import ExtractionStrategy


class JsonlPassthrough(ExtractionStrategy):
    name = "jsonl_passthrough"

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        text = source.decoded_text().lstrip("﻿")
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except ValueError as error:
                raise StrategyFailed(f"invalid JSONL record on line {number}: {error}") from error
        return StrategyOutput(text, "jsonl")
