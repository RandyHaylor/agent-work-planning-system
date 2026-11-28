"""FastAPI router for /guidance (spec: HTTP routes). Reads only.

Guidance is read from files, not the database, so these routes call prompt_builder's public
GuidanceService (the `guidance_service` dependency, filled in by the server) rather than
command_runner. Auth: any authenticated principal. Build log #58: all HTTP routing lives in http_api.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from planning_system.contract import NotFound, Principal
from planning_system.prompt_builder.guidance_interface import GuidanceService

from .dependencies import current_principal, guidance_service

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
