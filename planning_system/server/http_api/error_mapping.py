"""error_mapping: DomainError subclasses -> status + {"error": kind, "detail": message}.
Any other exception -> 500 with no internals in the body."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from planning_system.contract import Conflict, DomainError, Forbidden, Invalid, NotFound

ERROR_STATUS = {NotFound: 404, Forbidden: 403, Invalid: 422, Conflict: 409}

log = logging.getLogger(__name__)


def status_for(error: DomainError) -> int:
    for kind, status in ERROR_STATUS.items():
        if isinstance(error, kind):
            return status
    return 500


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, error: DomainError) -> JSONResponse:
        status = status_for(error)
        if status == 500:
            log.exception("unmapped domain error", exc_info=error)
            return JSONResponse({"error": "internal", "detail": "internal server error"}, status_code=500)
        return JSONResponse({"error": type(error).__name__, "detail": str(error)}, status_code=status)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, error: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=error)
        return JSONResponse({"error": "internal", "detail": "internal server error"}, status_code=500)
