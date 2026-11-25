"""router_mounting: mounts each router named in config at its prefix.
Config: "routers": [{"router": "pkg.module:router", "prefix": ""}, ...]."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import APIRouter, FastAPI

from planning_system.configuration import ConfigSection, import_object


@dataclass(frozen=True)
class RouterSpec:
    prefix: str
    router: APIRouter


def router_specs(section: ConfigSection) -> list[RouterSpec]:
    return [RouterSpec(entry.get("prefix", ""), import_object(entry["router"]))
            for entry in section.get("routers", [])]


def mount_routers(app: FastAPI, specs: Iterable[RouterSpec]) -> None:
    for spec in specs:
        app.include_router(spec.router, prefix=spec.prefix)
