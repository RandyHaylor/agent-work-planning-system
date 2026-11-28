"""agent_registry: every agent session referenced (spec: planning/05-spec-agent-registry.md).

Public surface: import from this package, not its files. `fakes` stays a separate
test-support submodule."""
from .interface import AgentRegistry
from .ports import AgentRegistryStoragePort, Clock
from .registry import AgentRegistryService
from .types import AgentId, AgentSession, METADATA_FIELDS

__all__ = ["AgentId", "AgentRegistry", "AgentRegistryService", "AgentRegistryStoragePort", "AgentSession",
           "Clock", "METADATA_FIELDS"]
