"""Server halt (build log #68): admin halts the whole system or one project; every write command and every review
hand-out is refused with Halted (423) while reads still work; halt/un-halt and admin log-in work while halted; the
check sits in one place (HaltGate, asked by CommandRunner)."""
from datetime import datetime, timezone

import pytest

from planning_system.contract import Forbidden, Halted, Principal
from planning_system.server import commands as C
from planning_system.server.commands.command_runner import CommandRunner
from planning_system.server.commands.fakes import FixedServicesFactory, fake_services
from planning_system.server.commands.request_authorizer import RequestAuthorizer
from planning_system.server.domain.system_halt import HaltSwitchService
from planning_system.server.domain.system_halt.fakes import InMemoryHaltStore
from planning_system.server.http_api.error_mapping import status_for
from planning_system.server.storage.fakes import InMemoryStorage

ADMIN = Principal(None, "admin")


class FixedClock:
    def now(self):
        return datetime(2026, 11, 28, tzinfo=timezone.utc)


@pytest.fixture
def world():
    storage = InMemoryStorage()
    services = fake_services(storage.stores)
    project = services.tree.create(None, "P", "what we're doing", "p")
    task = services.tree.create(project.id, "T", "high-level plan", "t")
    other = services.tree.create(None, "Q", "what we're doing", "q")
    other_task = services.tree.create(other.id, "U", "high-level plan", "u")
    runner = CommandRunner(storage.transactions, storage.stores_for, FixedServicesFactory(services),
                           RequestAuthorizer())
    return runner, services, project, task, other, other_task


def planner_of(project):
    return Principal("planner-1", "planner", project.id)


def test_halt_switch_state_and_refusal_message():
    switch = HaltSwitchService(InMemoryHaltStore(), FixedClock())
    switch.ensure_writable({1, None})
    state = switch.halt(4, "admin", "maze test")
    assert state.system is None and state.halted_project_ids == {4}
    switch.ensure_writable({1, None})
    with pytest.raises(Halted, match="project 4 was halted by admin .*maze test"):
        switch.ensure_writable({4})
    switch.halt(None, "admin")
    with pytest.raises(Halted, match="the system was halted"):
        switch.ensure_writable({None})
    assert switch.unhalt(None).system is None and switch.unhalt(4).projects == ()


def test_halted_maps_to_423():
    assert status_for(Halted("halted")) == 423


def test_system_halt_refuses_every_write_but_reads_work(world):
    runner, services, project, task, *_ = world
    runner.run(C.HaltSystem(None, "stop"), ADMIN)
    with pytest.raises(Halted):
        runner.run(C.UpdateNode(task.id, {"title": "new"}), ADMIN)                # admin writes too
    with pytest.raises(Halted):
        runner.run(C.CreateProject("R", "r"), ADMIN)
    with pytest.raises(Halted):
        runner.run(C.TakeReview(project.id), planner_of(project))                 # review hand-out
    assert runner.run(C.GetNode(task.id), planner_of(project)).title == "T"      # reads work
    assert runner.run(C.GetHaltState(), ADMIN).system.reason == "stop"
    assert services.tree.get(task.id).title == "T"


def test_admin_can_log_in_halt_and_unhalt_while_halted(world):
    runner, services, project, task, *_ = world
    runner.run(C.HaltSystem(None), ADMIN)
    runner.run(C.HaltSystem(project.id, "also this one"), ADMIN)
    with pytest.raises(Exception) as login:
        runner.run(C.StartAdminSession("wrong password"), None)
    assert not isinstance(login.value, Halted)                                     # reached the password check
    runner.run(C.UnhaltSystem(None), ADMIN)
    runner.run(C.UnhaltSystem(project.id), ADMIN)
    assert runner.run(C.UpdateNode(task.id, {"title": "new"}), ADMIN).title == "new"


def test_project_halt_refuses_writes_in_that_project_only(world):
    runner, services, project, task, other, other_task = world
    runner.run(C.HaltSystem(project.id), ADMIN)
    with pytest.raises(Halted):
        runner.run(C.UpdateNode(task.id, {"title": "x"}), ADMIN)                   # resolved from the node
    with pytest.raises(Halted):
        runner.run(C.TakeReview(project.id), ADMIN)                                 # named project
    with pytest.raises(Halted):
        runner.run(C.CreateNode(project.id, "N", "high-level plan", "n"), planner_of(project))
    assert runner.run(C.UpdateNode(other_task.id, {"title": "y"}), ADMIN).title == "y"
    runner.run(C.TakeReview(other.id), ADMIN)                                       # other project: not halted
    assert runner.run(C.CreateProject("R", "r"), ADMIN).title == "R"               # no project: system halt only


def test_only_admin_halts_or_unhalts(world):
    runner, services, project, *_ = world
    for command in (C.HaltSystem(None), C.UnhaltSystem(None), C.GetHaltState()):
        with pytest.raises(Forbidden):
            runner.run(command, planner_of(project))


def test_halt_survives_new_services_over_the_same_store(world):
    runner, services, project, task, *_ = world
    runner.run(C.HaltSystem(None, "durable"), ADMIN)
    store = services.halt._storage
    again = HaltSwitchService(store, FixedClock())
    with pytest.raises(Halted):
        again.ensure_writable({None})


def test_every_write_command_is_gated_except_the_admin_session_and_halt_commands():
    exempt = {cls for cls in C.ROUTES.values() if cls.allowed_while_halted}
    assert exempt == {C.StartAdminSession, C.EndAdminSession, C.HaltSystem, C.UnhaltSystem}
