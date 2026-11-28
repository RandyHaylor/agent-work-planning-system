"""response_shapes: the JSON a route returns where the command's domain result alone is not the shape
the api_client expects (build log #40). Protocol only: field naming and wrapping, no domain calls."""
from __future__ import annotations

from typing import Any

from planning_system.server.domain.references.citation_syntax import format_citation

from .json_encoding import to_json


def ended(_: Any) -> dict:
    return {"ended": True}


def revoked(credential_id: str):
    return lambda _: {"id": credential_id, "revoked": True}


def rotated(issued) -> dict:
    return {"id": issued.credential_id, **to_json(issued)}


def node_content(node_id: int, text: str):
    return lambda content: {"node_id": node_id, "text": text, **to_json(content)}


def assembled_context(context) -> dict:
    return {**to_json(context), "context": context.text}


def citation(cited) -> dict:
    return {**to_json(cited), "citation": format_citation(cited)}


def rendered(citation_text: str):
    return lambda text: {"citation": citation_text, "text": text}


def reference_id(reference) -> dict:
    return {"reference_id": reference.id, **to_json(reference)}
