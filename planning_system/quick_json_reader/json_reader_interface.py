"""Interfaces (ABCs) of the integration and its replaceable parts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from planning_system.quick_json_reader.json_reader_types import JsonReaderOutput, LineRange, NodeRunResult, TextKind


class JsonReaderInterface(ABC):
    @abstractmethod
    def run(self, stored_text: str, text_kind: TextKind, flags: Sequence[str]) -> JsonReaderOutput: ...


class NodeRunnerInterface(ABC):
    @abstractmethod
    def run(self, text: str, argv: Sequence[str]) -> NodeRunResult: ...


class JsonLineLocator(ABC):
    @abstractmethod
    def locate(self, address_steps: Sequence[int]) -> LineRange:
        """Raises KeyError for an unknown address."""


class JsonLineLocatorFactory(ABC):
    @abstractmethod
    def for_text(self, stored_text: str, text_kind: TextKind) -> JsonLineLocator: ...
