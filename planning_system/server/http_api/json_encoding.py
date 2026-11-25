"""Domain results -> JSON at the edge (dataclasses, frozensets, tuples, datetimes, enums)."""
from __future__ import annotations

import dataclasses
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping


def to_json(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((to_json(v) for v in value), key=repr)
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value
