from __future__ import annotations


def sniff_media_type(raw_bytes: bytes) -> str | None:
    """Magic bytes: %PDF-, PK..+word/ (docx), <!doctype html/<html, { or [ (JSON), after any BOM."""
    raise NotImplementedError("level 7")
