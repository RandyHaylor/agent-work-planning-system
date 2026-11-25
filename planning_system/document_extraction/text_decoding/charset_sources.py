"""Where a charset can be read from, each returning a codec name or None."""
from __future__ import annotations

import codecs
import re

_HEADER_CHARSET = re.compile(r"charset\s*=\s*[\"']?([\w.:-]+)", re.I)
_META_CHARSET = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?([\w.:-]+)", re.I)
_META_SCAN_BYTES = 4096
_BOMS = ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"), (codecs.BOM_UTF8, "utf-8-sig"),
         (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"))


def _known(name: str | None) -> str | None:
    if not name:
        return None
    try:
        return codecs.lookup(name).name
    except LookupError:
        return None


def header_charset(content_type_header: str | None) -> str | None:
    """`charset=` parameter of a Content-Type header."""
    match = _HEADER_CHARSET.search(content_type_header or "")
    return _known(match.group(1)) if match else None


def meta_charset(raw_bytes: bytes) -> str | None:
    """`<meta charset>` or `<meta http-equiv="Content-Type" content="...charset=...">` in the leading bytes."""
    match = _META_CHARSET.search(raw_bytes[:_META_SCAN_BYTES])
    return _known(match.group(1).decode("ascii", "ignore")) if match else None


def bom_charset(raw_bytes: bytes) -> str | None:
    """UTF-8/16/32 byte-order mark."""
    for bom, name in _BOMS:
        if raw_bytes.startswith(bom):
            return name
    return None
