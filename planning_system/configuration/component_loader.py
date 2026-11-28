"""component_loader: imports the factory named in a section ("factory": "pkg.module:callable") and
calls it with exactly that section."""
from __future__ import annotations

import importlib
from typing import Any, Callable, Protocol

from planning_system.errors import Invalid

from .section import ConfigSection


class Component(Protocol):
    """What every top-level factory returns."""

    def commands(self) -> dict[str, Callable[[list[str]], int]]: ...


def import_object(dotted: str) -> Any:
    """"pkg.module:attribute" -> the attribute."""
    module_name, sep, attribute = dotted.partition(":")
    if not sep or not module_name or not attribute:
        raise Invalid(f"{dotted!r} is not of the form 'package.module:name'")
    try:
        target: Any = importlib.import_module(module_name)
    except ImportError as error:
        raise Invalid(f"cannot import {module_name!r} ({error})") from error
    for part in attribute.split("."):
        if not hasattr(target, part):
            raise Invalid(f"{module_name!r} has no {attribute!r}")
        target = getattr(target, part)
    return target


def load_component(section: ConfigSection) -> Component:
    factory = import_object(section.get("factory"))
    return factory(section)
