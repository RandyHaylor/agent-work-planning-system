from __future__ import annotations


def media_type_from_header(content_type_header: str | None) -> str | None:
    """Media type only, lower-cased, parameters dropped."""
    if not content_type_header:
        return None
    media_type = content_type_header.split(";", 1)[0].strip().lower()
    return media_type if "/" in media_type else None
