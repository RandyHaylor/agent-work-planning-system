"""Contract tests for agent_registry (spec: planning/05-spec-agent-registry.md); mocked storage."""
import pytest

from planning_system.server.domain.agent_registry.fakes import (FakeAgentRegistry, FakeClock,
                                                                InMemoryAgentRegistryStorage)
from planning_system.server.domain.agent_registry.interface import AgentRegistry
from planning_system.server.domain.agent_registry.ports import AgentRegistryStoragePort
from planning_system.server.domain.agent_registry.registry import AgentRegistryService

@pytest.fixture(params=["fake", "real"])
def setup(request):
    storage, clock = InMemoryAgentRegistryStorage(), FakeClock()
    cls = FakeAgentRegistry if request.param == "fake" else AgentRegistryService
    return cls(storage, clock), clock


def test_1_register_new_id_sets_first_seen_equal_last_seen(setup):
    registry, _ = setup
    session = registry.register("a1", host="box", platform="claude-code")
    assert session.first_seen == session.last_seen
    assert registry.get("a1") == session
    assert [s.agent_id for s in registry.list()] == ["a1"]


def test_2_register_existing_updates_fields_and_last_seen_keeps_first_seen(setup):
    registry, clock = setup
    first = registry.register("a1", model="m1")
    clock.advance()
    second = registry.register("a1", model="m2")
    assert second.model == "m2"
    assert second.first_seen == first.first_seen
    assert second.last_seen > first.last_seen


def test_3_fields_not_given_stay(setup):
    registry, clock = setup
    registry.register("a1", host="box", path="/work", url="u")
    clock.advance()
    updated = registry.register("a1", model="m1")
    assert (updated.host, updated.path, updated.url, updated.model) == ("box", "/work", "u", "m1")


def test_4_no_way_to_delete(setup):
    registry, _ = setup
    registry.register("a1")
    for name in ("delete", "remove", "unregister"):
        assert not hasattr(registry, name)
        assert not hasattr(AgentRegistry, name)
        assert not hasattr(AgentRegistryStoragePort, name)
    assert registry.get("a1").agent_id == "a1"
