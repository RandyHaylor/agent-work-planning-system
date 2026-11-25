"""section: ConfigSection, a read-only view of one config section. Only the module that owns a
section interprets it; nobody else looks inside."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from planning_system.contract import Invalid

MISSING = object()


class ConfigSection:
    def __init__(self, name: str, values: Mapping[str, Any], origin: str = ""):
        self.name = name
        self._values = dict(values)
        self._origin = origin          # where it came from, for error messages

    def get(self, key: str, default: Any = MISSING) -> Any:
        if key in self._values:
            return copy.deepcopy(self._values[key])
        if default is MISSING:
            raise Invalid(f"config section {self.name!r} has no key {key!r}{self._where()}")
        return default

    def child(self, name: str) -> "ConfigSection":
        value = self._values.get(name)
        if not isinstance(value, Mapping):
            raise Invalid(f"config section {self._qualified(name)!r} is missing{self._where()}")
        return ConfigSection(self._qualified(name), value, self._origin)

    def has(self, key: str) -> bool:
        return key in self._values

    def as_dict(self) -> dict:
        return copy.deepcopy(self._values)

    def _qualified(self, name: str) -> str:
        return f"{self.name}.{name}" if self.name else name

    def _where(self) -> str:
        return f" (config folder {self._origin})" if self._origin else ""

    def __repr__(self) -> str:
        return f"ConfigSection({self.name!r})"
