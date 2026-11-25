"""Contract tests for task_assignment, server part (spec: planning/05-spec-task-assignment.md, tests 1-5).
Tests 6-8 (task start/stop) belong to local_client's task_runner and live there."""
import pytest

from planning_system.contract import Forbidden, Invalid, Principal
from planning_system.server.commands.fakes import fake_services
from planning_system.server.domain.task_assignment.fakes import FakeTaskAssigner
from planning_system.server.domain.task_assignment.task_assigner import TaskAssignerService



class FailingIssuer:
    def __init__(self, inner):
        self.inner = inner

    def mint(self, *args, **kwargs):
        raise Forbidden("mint failed")


@pytest.fixture(params=["fake", "real"])
def world(request):
    services = fake_services()
    cls = FakeTaskAssigner if request.param == "fake" else TaskAssignerService
    project = services.tree.create(None, "P", "what we're doing", "p")
    task = services.tree.create(project.id, "T", "high-level plan", "t")
    return {"s": services, "assigner": cls(services.tree, services.issuer, services.agents), "cls": cls,
            "project": project, "task": task,
            "planner": Principal("planner-1", "planner", project.id)}


def test_1_assign_sets_assignee_branch_state_and_returns_a_working_worker_token(world):
    s, task = world["s"], world["task"]
    result = world["assigner"].assign(world["planner"], task.id, "agent-9", "feat/x")
    assert (result.node.assignee, result.node.branch, result.node.state) == ("agent-9", "feat/x", "assigned")
    who = s.issuer.authenticate(result.worker_token)
    assert (who.role, who.scope_node_id, who.agent_id) == ("worker", task.id, "agent-9")
    assert s.agents.get("agent-9").agent_id == "agent-9"


def test_2_planner_outside_its_project_and_worker_cannot_assign(world):
    s = world["s"]
    other = s.tree.create(None, "Other", "what we're doing", "o")
    outsider = Principal("planner-2", "planner", other.id)
    worker = Principal("w", "worker", world["project"].id, world["task"].id)
    for who in (outsider, worker):
        with pytest.raises(Forbidden):
            world["assigner"].assign(who, world["task"].id, "agent-9", "b")


@pytest.mark.parametrize("state", ["done", "abandoned"])
def test_3_assigning_a_done_or_abandoned_node_is_invalid(world, state):
    world["s"].tree.set_state(world["task"].id, state)
    with pytest.raises(Invalid):
        world["assigner"].assign(world["planner"], world["task"].id, "agent-9", "b")


def test_3b_a_node_with_children_is_not_a_task(world):
    with pytest.raises(Invalid):
        world["assigner"].assign(world["planner"], world["project"].id, "agent-9", "b")


def test_4_failed_mint_leaves_the_node_unchanged(world):
    s, task = world["s"], world["task"]
    before = s.tree.get(task.id)
    assigner = world["cls"](s.tree, FailingIssuer(s.issuer), s.agents)
    with pytest.raises(Forbidden):
        assigner.assign(world["planner"], task.id, "agent-9", "b")
    assert s.tree.get(task.id) == before


def test_5_revoking_the_planner_revokes_the_worker_tokens_it_minted(world):
    s = world["s"]
    admin = Principal(None, "admin")
    planner_cred = s.issuer.mint(admin, "planner", world["project"].id, None, "planner-1")
    planner = s.issuer.authenticate(planner_cred.token)
    result = world["assigner"].assign(planner, world["task"].id, "agent-9", "b")
    s.issuer.revoke(admin, planner_cred.credential_id)
    with pytest.raises(Forbidden):
        s.issuer.authenticate(result.worker_token)
