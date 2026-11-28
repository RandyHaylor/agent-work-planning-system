"""adapter_for(config): picks the harness adapter for this install."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .ai_cli_adapter_interface import AiCliAdapterInterface
from .process_tracker import ProcessTracker
from .types import AdapterConfig


def adapter_for(config: AdapterConfig, session_logs_directory: Optional[Path] = None,
                process_tracker: Optional[ProcessTracker] = None) -> AiCliAdapterInterface:
    """process_tracker: told about every reviewer process the adapter launches (`planning halt` finds them)."""
    if config.harness == "claude_code":
        from .claude_code import ClaudeCodeAdapter

        return ClaudeCodeAdapter(session_logs_directory=session_logs_directory, process_tracker=process_tracker)
    raise ValueError(f"no harness adapter for {config.harness!r} (v1 supports 'claude_code')")
