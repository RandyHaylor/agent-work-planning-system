"""FastAPI router for /reader/* and /references/* (commands.catalog.REFERENCE_ROUTES). Protocol only:
read the request, build a command, run it through the CommandRunner, return JSON."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from planning_system.contract import Principal
from planning_system.server import commands as C
from planning_system.server.http_api.dependencies import command_runner, current_principal
from planning_system.server.http_api.json_encoding import to_json

router = APIRouter(tags=["reader", "references"])

Who = Depends(current_principal)
Runner = Depends(command_runner)


class LoadBody(BaseModel):
    url: Optional[str] = None
    file_name: Optional[str] = None
    file_base64: Optional[str] = None
    search_terms: Optional[str] = None
    strategy: Optional[str] = None
    line_start: Optional[int] = None
    line_count: Optional[int] = None


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="allow")      # fastReader search options pass through
    terms: str
    ids: list[str] = Field(default_factory=list)


class JsonBody(BaseModel):
    flags: list[str] = Field(default_factory=list)


class CiteBody(BaseModel):
    id: str
    start_line: int
    end_line: int


class RenderBody(BaseModel):
    citation: str


class UserExchangeBody(BaseModel):
    session_id: str
    user_message: str
    pre_text: str


def _run(runner, command, principal) -> Any:
    return to_json(runner.run(command, principal))


# ---- reader

@router.post("/reader/load")
def load_into_reader(body: LoadBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.LoadIntoReader(**body.model_dump()), principal)


@router.post("/reader/search")
def reader_search(body: SearchBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReaderSearch(body.terms, tuple(body.ids), dict(body.model_extra or {})), principal)


@router.post("/reader/cite")
def cite_cache_item(body: CiteBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.CiteCacheItem(body.id, body.start_line, body.end_line), principal)


@router.get("/reader/{reader_id}/toc")
def reader_toc(reader_id: str, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReaderToc(reader_id), principal)


@router.get("/reader/{reader_id}/get")
def reader_get(reader_id: str, request: Request, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReaderGet(reader_id, dict(request.query_params)), principal)


@router.post("/reader/{reader_id}/json")
def reader_json(reader_id: str, body: JsonBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReaderJson(reader_id, tuple(body.flags)), principal)


@router.get("/reader/{reader_id}/lines")
def reader_lines(reader_id: str, start: Optional[int] = None, end: Optional[int] = None,
                 principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReaderLines(reader_id, start, end), principal)


# ---- references (fixed paths before /{reference_id})

@router.post("/references/render")
def render_citation(body: RenderBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.RenderCitation(body.citation), principal)


@router.post("/references/user-exchange")
def store_user_exchange(body: UserExchangeBody, principal: Principal = Who, runner=Runner):
    return _run(runner, C.StoreUserExchange(body.session_id, body.user_message, body.pre_text), principal)


@router.get("/references/{reference_id}")
def get_reference(reference_id: str, follow_superseded: bool = False, principal: Principal = Who,
                  runner=Runner):
    return _run(runner, C.GetReference(reference_id, follow_superseded), principal)


@router.get("/references/{reference_id}/lines")
def read_reference_lines(reference_id: str, start: Optional[int] = None, end: Optional[int] = None,
                         principal: Principal = Who, runner=Runner):
    return _run(runner, C.ReadReferenceLines(reference_id, start, end), principal)
