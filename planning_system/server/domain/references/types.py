"""reference_types: Reference (one fixed item), Citation (reference id + line range), temp cache entry."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

ReferenceId = str
CacheId = str
AgentId = str
NodeId = int

ORIGIN_USER_EXCHANGE = "user_exchange"
ORIGIN_PROPOSAL_RESPONSE = "proposal_response"
ORIGIN_NODE = "node"
ORIGIN_DOCUMENT = "document"            # anything the reader loaded and an agent cited
ORIGIN_KNOWLEDGE_BASE = "knowledge_base"


@dataclass(frozen=True)
class Reference:
    id: ReferenceId
    origin: str
    text: str
    sha256: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    owner: Optional[AgentId] = None
    superseded_by: Optional[ReferenceId] = None


@dataclass(frozen=True)
class Citation:
    reference_id: ReferenceId
    start_line: int                  # 1-based, inclusive
    end_line: int                    # 1-based, inclusive


@dataclass(frozen=True)
class TempCacheEntry:
    """One item in an agent's temp cache (visible to that agent + admin; wiped freely)."""
    cache_id: CacheId
    owner: AgentId
    text: str
    sha256: str
    created_at: datetime
    metadata: Mapping[str, str] = field(default_factory=dict)
