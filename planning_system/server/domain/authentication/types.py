"""Types for authentication."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from planning_system.contract import Principal

CredentialId = str
AgentId = str

KIND_AGENT = "agent"                 # planner / worker session key (persistent)
KIND_ADMIN_SESSION = "admin_session" # temporary
KIND_QUOTE_KEY = "quote_key"         # per install


@dataclass(frozen=True)
class IssuedCredential:
    token: str                       # plaintext, shown once at mint/rotate
    credential_id: CredentialId
    principal: Principal


@dataclass(frozen=True)
class StoredCredential:
    """What credential storage holds: the digest only, never the plaintext."""
    credential_id: CredentialId
    token_digest: str
    principal: Principal
    kind: str
    minted_by: Optional[AgentId] = None      # agent_id of the issuer (for cascading revoke)
    label: Optional[str] = None              # e.g. the quote key's install label
    revoked: bool = False
    expires_at: Optional[datetime] = None    # admin sessions only
