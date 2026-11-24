# Spec: agent_registry

APPROVED by the user, 2026-11-23, in Slack: "approve agent_registry".

From your words: "a running registry (a table/list) of all the agent sessions we reference, keyed by that ID, with typical optional metadata fields such as host, platform, model, path, system and URL"; "simple and quick"; "Never delete entries".

```python
@dataclass(frozen=True)
class AgentSession:
    agent_id: AgentId
    host: str | None = None
    platform: str | None = None      # e.g. claude-code, codex, web
    model: str | None = None
    path: str | None = None          # working folder
    system: str | None = None        # OS
    url: str | None = None
    first_seen: datetime
    last_seen: datetime

class AgentRegistry:
    def register(self, agent_id, **metadata) -> AgentSession   # new, or updates metadata + last_seen
    def get(self, agent_id) -> AgentSession
    def list(self) -> list[AgentSession]
    # no delete
```

## External integration tests (mocked storage)

1. register on a new ID creates an entry with first_seen = last_seen.
2. register on an existing ID updates the given fields and last_seen, and keeps first_seen.
3. Fields not given stay as they were (optional metadata).
4. There is no way to delete an entry.
