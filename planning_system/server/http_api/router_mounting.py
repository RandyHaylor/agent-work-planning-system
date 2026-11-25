"""router_mounting: mounts each router named in config at its prefix.
Config: "routers": [{"router": "pkg.module:router", "prefix": ""}, ...]."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from planning_system.configuration import ConfigSection, import_object


@dataclass(frozen=True)
class RouterSpec:
    prefix: str
    router: APIRouter


def router_specs(section: ConfigSection) -> list[RouterSpec]:
    return [RouterSpec(entry.get("prefix", ""), import_object(entry["router"]))
            for entry in section.get("routers", [])]


def mount_routers(app: FastAPI, specs: Iterable[RouterSpec]) -> None:
    """Each route is added to the app directly. FastAPI >= 0.16x includes routers lazily (one
    `_IncludedRouter` entry in app.routes), which hides the served routes from app.routes."""
    for spec in specs:
        for route in spec.router.routes:
            if isinstance(route, APIRoute):
                app.router.add_api_route(
                    spec.prefix + route.path, route.endpoint, methods=sorted(route.methods),
                    name=route.name, tags=route.tags, dependencies=route.dependencies,
                    response_model=route.response_model, status_code=route.status_code,
                    summary=route.summary, description=route.description,
                    include_in_schema=route.include_in_schema)
            else:
                app.router.routes.append(route)
