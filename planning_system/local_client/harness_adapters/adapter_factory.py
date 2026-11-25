"""adapter_for(config): picks the harness adapter for this install. Level 6 scaffold: hollow."""
from __future__ import annotations

from .ai_cli_adapter_interface import AiCliAdapterInterface
from .types import AdapterConfig


def adapter_for(config: AdapterConfig) -> AiCliAdapterInterface:
    raise NotImplementedError("level 7")
