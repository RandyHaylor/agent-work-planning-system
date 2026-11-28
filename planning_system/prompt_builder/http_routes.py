"""FastAPI router for /guidance (spec: HTTP routes). Reads only.

Guidance is read from files, not the database, so these routes use the module's own
`guidance_service` dependency (overridden by the server at mount time) rather than
command_runner; auth is this module's own `current_principal` placeholder (any authenticated
principal), which the server overrides with its own, so this module never imports the server.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from planning_system.contract import NotFound, Principal
from planning_system.prompt_builder.guidance_interface import GuidanceService


def current_principal() -> Principal:  # filled in by the server (dependency_overrides)
    raise NotImplementedError


def guidance_service() -> GuidanceService:  # filled in by the server (dependency_overrides)
    raise NotImplementedError


router = APIRouter(prefix="/guidance", tags=["guidance"])


# Fixed paths come before /{role} so they are not taken as role names.
@router.get("/templates")
def get_templates(_: Principal = Depends(current_principal),
                  service: GuidanceService = Depends(guidance_service)) -> dict:
    return service.templates()


@router.get("/rules")
def get_rules(_: Principal = Depends(current_principal),
              service: GuidanceService = Depends(guidance_service)) -> list:
    return service.rules()


@router.get("/{role}")
def get_role_guidance(role: str, _: Principal = Depends(current_principal),
                      service: GuidanceService = Depends(guidance_service)) -> dict:
    try:
        return asdict(service.guidance_for(role))
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
