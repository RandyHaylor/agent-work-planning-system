"""Types for agent_registry."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

AgentId = str

METADATA_FIELDS = ("host", "platform", "model", "path", "system", "url")


@dataclass(frozen=True, kw_only=True)
class AgentSession:
    agent_id: AgentId
    host: Optional[str] = None
    platform: Optional[str] = None   # e.g. claude-code, codex, web
    model: Optional[str] = None
    path: Optional[str] = None       # working folder
    system: Optional[str] = None     # OS
    url: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
