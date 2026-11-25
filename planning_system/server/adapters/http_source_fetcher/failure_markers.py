from __future__ import annotations

from typing import Mapping


def failure_reason(status: int, headers: Mapping[str, str], body: bytes) -> str | None:
    """status >= 400 -> "http <status>"; `cf-mitigated: challenge` -> "cloudflare challenge (cf-mitigated)";
    empty body -> "empty body"; else None."""
    raise NotImplementedError("level 7")
