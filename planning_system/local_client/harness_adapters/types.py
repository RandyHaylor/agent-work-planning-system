"""harness_adapters types (spec: planning/05-spec-local-client.md)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class HeadlessSessionSpec:
    session_id: str                     # = agent_id registered on the server
    working_directory: Path
    environment: Mapping[str, str] = field(repr=False)  # PLANNING_URL, PLANNING_TOKEN, PLANNING_CA_CERT
    allowed_tools: tuple[str, ...] = ()
    allowed_read_paths: tuple[Path, ...] = ()
    model: Optional[str] = None


@dataclass(frozen=True)
class AdapterConfig:
    """Which harness this install uses. Only "claude_code" in v1 (codex later, same interface)."""
    harness: str = "claude_code"
