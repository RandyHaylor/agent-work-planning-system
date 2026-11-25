from __future__ import annotations

import json

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_BOMS = (b"\xef\xbb\xbf", b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff", b"\xff\xfe", b"\xfe\xff")
_HEAD = 1024


def _strip_bom(raw_bytes: bytes) -> bytes:
    for bom in _BOMS:
        if raw_bytes.startswith(bom):
            return raw_bytes[len(bom):]
    return raw_bytes


def _json_kind(body: bytes) -> str | None:
    """application/json if the whole body parses; application/jsonl if every non-blank line does."""
    try:
        json.loads(body)
        return "application/json"
    except ValueError:
        pass
    lines = [line for line in body.splitlines() if line.strip()]
    try:
        for line in lines:
            json.loads(line)
    except ValueError:
        return None
    return "application/jsonl" if len(lines) > 1 else None


def sniff_media_type(raw_bytes: bytes) -> str | None:
    """Magic bytes: %PDF-, PK..+word/ (docx), <!doctype html/<html, { or [ (JSON), after any BOM."""
    body = _strip_bom(raw_bytes)
    head = body[:_HEAD].lstrip()
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if body.startswith(b"PK\x03\x04") and b"word/" in body:
        return DOCX
    if head.lower().startswith((b"<!doctype html", b"<html")):
        return "text/html"
    if head[:1] in (b"{", b"["):
        return _json_kind(body)
    return None
