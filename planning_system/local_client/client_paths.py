"""client_paths: where this install keeps its local files (one config dir; PLANNING_CLIENT_HOME overrides)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

ENV_CLIENT_HOME = "PLANNING_CLIENT_HOME"
DEFAULT_CLIENT_HOME = Path.home() / ".planning-client"


class ClientPaths:
    """Every local file the client writes lives under one directory."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home is not None else DEFAULT_CLIENT_HOME

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] = os.environ) -> "ClientPaths":
        configured = environment.get(ENV_CLIENT_HOME)
        return cls(Path(configured).expanduser() if configured else None)

    @property
    def exchange_cache_file(self) -> Path:          # quote_capture's local cache
        return self.home / "exchanges.jsonl"

    @property
    def running_sessions_file(self) -> Path:        # task_runner's registry
        return self.home / "running-sessions.json"

    @property
    def session_logs_directory(self) -> Path:       # stream-json output of headless sessions
        return self.home / "sessions"

    @property
    def reviewer_thinking_log_file(self) -> Path:   # review_worker's log
        return self.home / "reviewer-thinking.log"
