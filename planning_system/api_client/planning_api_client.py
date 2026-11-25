"""PlanningApiClient: facade, one thin method per route; each builds the request and hands it to HttpTransport.

Level 6 scaffold: hollow (every method raises NotImplementedError).
"""
from __future__ import annotations

from typing import Optional

import httpx

from .http_transport import HttpTransport
from .interface import PlanningApiClientInterface
from .types import ClientSettings


def _hollow(*_args, **_kwargs):
    raise NotImplementedError("level 7")


class PlanningApiClient(PlanningApiClientInterface):

    def __init__(self, settings: ClientSettings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._http = HttpTransport(settings, transport)

    with_token = _hollow
    tls_verify = property(_hollow)

    start_admin_session = _hollow
    end_admin_session = _hollow
    me = _hollow
    mint_credential = _hollow
    mint_quote_key = _hollow
    revoke_credential = _hollow
    rotate_credential = _hollow
    register_agent = _hollow

    create_project = _hollow
    create_node = _hollow
    nodes_by_state = _hollow
    get_node = _hollow
    children = _hollow
    ancestors = _hollow
    ready_children = _hollow
    update_node = _hollow
    move_node = _hollow
    set_state = _hollow
    assign = _hollow
    create_supplementary_task = _hollow
    add_content = _hollow
    replace_content = _hollow
    context = _hollow

    reader_load = _hollow
    reader_toc = _hollow
    reader_get = _hollow
    reader_search = _hollow
    reader_json = _hollow
    reader_lines = _hollow
    reader_cite = _hollow
    get_reference = _hollow
    reference_lines = _hollow
    render_citation = _hollow
    store_user_exchange = _hollow

    guidance = _hollow
    guidance_templates = _hollow
    guidance_rules = _hollow
