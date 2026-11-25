"""Shared fixtures for local_client contract tests: fake server, planner api, fake adapter."""
from __future__ import annotations

import pytest

from planning_system.api_client import ClientSettings
from planning_system.api_client.fakes import FakePlanningApiClient, FakePlanningServer
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter


@pytest.fixture
def server():
    return FakePlanningServer()


@pytest.fixture
def settings(server):
    return ClientSettings("https://127.0.0.1:8443", None, server.issue_token("planner", agent_id="planner-1"))


@pytest.fixture
def api(server, settings):
    return FakePlanningApiClient(settings, transport=server.transport())


@pytest.fixture
def task_node(server):
    project = server.seed_project("Proj")
    return server._new_node(project["id"], "Build the thing", "task", "build it", [], None)


@pytest.fixture
def adapter():
    return FakeAiCliAdapter()
