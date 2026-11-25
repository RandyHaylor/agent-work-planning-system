"""Where a charset can be read from, each returning a codec name or None."""
from __future__ import annotations


def header_charset(content_type_header: str | None) -> str | None:
    """`charset=` parameter of a Content-Type header."""
    raise NotImplementedError("level 7")


def meta_charset(raw_bytes: bytes) -> str | None:
    """`<meta charset>` or `<meta http-equiv="Content-Type" content="...charset=...">` in the leading bytes."""
    raise NotImplementedError("level 7")


def bom_charset(raw_bytes: bytes) -> str | None:
    """UTF-8/16/32 byte-order mark."""
    raise NotImplementedError("level 7")
