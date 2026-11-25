"""adapter_for(config): picks the harness adapter for this install."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .ai_cli_adapter_interface import AiCliAdapterInterface
from .types import AdapterConfig


def adapter_for(config: AdapterConfig, session_logs_directory: Optional[Path] = None) -> AiCliAdapterInterface:
    if config.harness == "claude_code":
        from .claude_code import ClaudeCodeAdapter

        return ClaudeCodeAdapter(session_logs_directory=session_logs_directory)
    raise ValueError(f"no harness adapter for {config.harness!r} (v1 supports 'claude_code')")
