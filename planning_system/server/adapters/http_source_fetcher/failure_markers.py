from __future__ import annotations

from typing import Mapping

_HTTP_ERROR_FROM = 400


def failure_reason(status: int, headers: Mapping[str, str], body: bytes) -> str | None:
    """status >= 400 -> "http <status>"; `cf-mitigated: challenge` -> "cloudflare challenge (cf-mitigated)";
    empty body -> "empty body"; else None."""
    lowered = {key.lower(): value for key, value in headers.items()}
    if lowered.get("cf-mitigated", "").strip().lower() == "challenge":
        return "cloudflare challenge (cf-mitigated)"
    if status >= _HTTP_ERROR_FROM:
        return f"http {status}"
    if not body:
        return "empty body"
    return None
