"""Contract tests for commands (spec: planning/05-spec-commands.md). Mocked Transactions and services
(domain fakes). CommandRunner is thin real code and runs now; the authorizer runs [fake, real(xfail)];
command bodies are hollow, so the tests that run them are real-only xfail."""
import dataclasses
import importlib
import inspect
import pkgutil
import re
from pathlib import Path

import pytest

from planning_system.contract import Forbidden, Invalid, Principal
from planning_system.server import commands as C
from planning_system.server.commands import permissions as P
from planning_system.server.commands.catalog import CORE_ROUTES, REFERENCE_ROUTES, ROUTES
from planning_system.server.commands.command import Access, Command
from planning_system.server.commands.command_runner import CommandRunner
from planning_system.server.commands.fakes import (FakeRequestAuthorizer, FixedServicesFactory,
                                                   fake_services)
from planning_system.server.commands.request_authorizer import RequestAuthorizer
from planning_system.server.storage.fakes import InMemoryStorage

LEVEL7 = pytest.mark.xfail(strict=False, reason="level 7")
REPO = Path(__file__).resolve().parents[3]
ADMIN = Principal(None, "admin")


class AllowAll:
    def check(self, principal, permission, services):
        pass


class DenyAll:
    def check(self, principal, permission, services):
        raise Forbidden("no")


@dataclasses.dataclass(frozen=True)
class Probe(C.ReadCommand):
    result: object = "ok"
    error: object = None

    def required_permission(self):
        return P.Authenticated()

    def run(self, services, principal):
        if self.error:
            raise self.error
        return self.result


@dataclasses.dataclass(frozen=True)
class WriteProbe(Probe):
    access = Access.WRITE


def runner(authorizer=None, services=None):
    storage = InMemoryStorage()
    factory = FixedServicesFactory(services or fake_services(storage.stores))
    return CommandRunner(storage.transactions, storage.stores_for, factory, authorizer or AllowAll()), storage


# ---- runner (1-3)

def test_1_read_runs_read_only_write_runs_read_write():
    r, storage = runner()
    assert r.run(Probe(), ADMIN) == "ok"
    assert r.run(WriteProbe(), ADMIN) == "ok"
    assert [t.mode for t in storage.transactions.records] == ["read_only", "read_write"]


def test_2_forbidden_stops_before_run_and_nothing_commits():
    r, storage = runner(DenyAll())
    ran = []

    @dataclasses.dataclass(frozen=True)
    class Spy(WriteProbe):
        def run(self, services, principal):
            ran.append(1)

    with pytest.raises(Forbidden):
        r.run(Spy(), ADMIN)
    assert ran == [] and storage.transactions.records[0].committed is False


def test_3_error_in_run_rolls_back():
    r, storage = runner()
    with pytest.raises(Invalid):
        r.run(WriteProbe(error=Invalid("bad")), ADMIN)
    assert storage.transactions.records[0].rolled_back


# ---- table (4)

def test_4_every_spec_route_has_exactly_one_command_and_every_command_is_routed():
    spec = (REPO / "planning" / "05-spec-commands.md").read_text()
    rows = re.findall(r"^\| (GET|POST|PUT|PATCH|DELETE) (\S+) \| (?:reader_view/)?(\w+)", spec, re.M)
    norm = lambda path: re.sub(r"\{[^}]+\}", "{}", path)
    table = {(m, norm(p)): cls.__name__ for (m, p), cls in ROUTES.items()}
    for method, path, name in rows:
        if path.startswith("/guidance"):
            continue                      # guidance is read through guidance_service (log #25)
        assert table.get((method, norm(path))) == name, (method, path)
    for extra in [("POST", "/credentials/{}/rotate"), ("DELETE", "/admin/sessions"), ("GET", "/nodes")]:
        assert extra in table             # log #17
    assert len(set(ROUTES.values())) == len(ROUTES)
    command_classes = set()
    for info in pkgutil.walk_packages(C.__path__, C.__name__ + "."):
        module = importlib.import_module(info.name)
        command_classes |= {obj for obj in vars(module).values()
                            if isinstance(obj, type) and issubclass(obj, Command)
                            and obj.__module__ == module.__name__ and not inspect.isabstract(obj)}
    assert command_classes == set(ROUTES.values())


def test_4b_reads_are_read_commands_and_gets_are_reads():
    for (method, _), cls in ROUTES.items():
        if method == "GET":
            assert cls.access is Access.READ, cls
    assert C.RenderCitation.access is Access.READ


def test_command_validation_happens_at_construction():
    with pytest.raises(Invalid):
        C.LoadIntoReader()
    with pytest.raises(Invalid):
        C.LoadIntoReader(url="u", search_terms="s")
    with pytest.raises(Invalid):
        C.CreateSupplementaryTask(1, "review", "t", "c")
    assert C.LoadIntoReader(file_name="a.txt", file_base64="eA==").file_name == "a.txt"


# ---- authorizer (6-9)

@pytest.fixture(params=["fake", pytest.param("real", marks=LEVEL7)])
def authorizer(request):
    return FakeRequestAuthorizer() if request.param == "fake" else RequestAuthorizer()


@pytest.fixture
def world():
    s = fake_services()
    project = s.tree.create(None, "P", "what we're doing", "p")
    task = s.tree.create(project.id, "T", "high-level plan", "t")
    other = s.tree.create(None, "Q", "what we're doing", "q")
    other_task = s.tree.create(other.id, "U", "high-level plan", "u")
    return dict(s=s, project=project, task=task, other_task=other_task,
                planner=Principal("pl", "planner", project.id),
                worker=Principal("wk", "worker", project.id, task.id),
                quote=Principal(None, "quote_client"))


def check(authorizer, world, principal, command):
    authorizer.check(principal, command.required_permission(), world["s"])


def test_6_worker_may_create_supplementary_only_on_its_own_task(authorizer, world):
    check(authorizer, world, world["worker"], C.CreateSupplementaryTask(world["task"].id, "tech_spike", "t", "c"))
    with pytest.raises(Forbidden):
        check(authorizer, world, world["worker"],
              C.CreateSupplementaryTask(world["other_task"].id, "tech_spike", "t", "c"))


def test_7_reader_ids_temp_for_owner_or_admin_reference_for_readers(authorizer, world):
    s = world["s"]
    entry = s.temp_cache.put("wk", "line1\nline2", {})
    check(authorizer, world, world["worker"], C.ReaderToc(entry.cache_id))
    check(authorizer, world, ADMIN, C.ReaderLines(entry.cache_id, 1, 2))
    with pytest.raises(Forbidden):
        check(authorizer, world, world["planner"], C.ReaderToc(entry.cache_id))
    other = s.temp_cache.put("someone", "x", {})
    citation = s.temp_cache.cite(other.cache_id, 1, 1)
    check(authorizer, world, ADMIN, C.ReaderGet(citation.reference_id))
    with pytest.raises(Forbidden):
        check(authorizer, world, world["worker"], C.ReaderSearch("x", (entry.cache_id, citation.reference_id)))


def test_8_only_start_admin_session_runs_without_a_principal(authorizer, world):
    check(authorizer, world, None, C.StartAdminSession("pw"))
    for command in (C.GetCurrentPrincipal(), C.GetNode(world["task"].id), C.LoadIntoReader(url="u"),
                    C.StoreUserExchange("s", "m", "p"), C.RegisterAgent("a")):
        with pytest.raises(Forbidden):
            check(authorizer, world, None, command)


def test_9_user_exchange_needs_the_quote_key_and_quote_key_minting_needs_admin(authorizer, world):
    check(authorizer, world, world["quote"], C.StoreUserExchange("s", "m", "p"))
    with pytest.raises(Forbidden):
        check(authorizer, world, world["planner"], C.StoreUserExchange("s", "m", "p"))
    check(authorizer, world, ADMIN, C.MintQuoteKey("laptop"))
    with pytest.raises(Forbidden):
        check(authorizer, world, world["planner"], C.MintQuoteKey("laptop"))


def test_planner_bounded_to_its_project(authorizer, world):
    check(authorizer, world, world["planner"], C.AssignTask(world["task"].id, "a", "b"))
    check(authorizer, world, world["planner"], C.CreateNode(world["task"].id, "x", "build", "c"))
    for command in (C.AssignTask(world["other_task"].id, "a", "b"), C.GetNode(world["other_task"].id),
                    C.CreateProject("t", "c")):
        with pytest.raises(Forbidden):
            check(authorizer, world, world["planner"], command)
    with pytest.raises(Forbidden):
        check(authorizer, world, world["worker"], C.AssignTask(world["task"].id, "a", "b"))


# ---- command bodies (hollow until level 7)

@LEVEL7
def test_5_assign_task_assigns_and_mints_in_the_same_transaction(world):
    s = world["s"]
    r, storage = runner(FakeRequestAuthorizer(), s)
    result = r.run(C.AssignTask(world["task"].id, "agent-9", "feat/x"), world["planner"])
    assert result.node.assignee == "agent-9"
    assert s.issuer.authenticate(result.worker_token).scope_node_id == world["task"].id
    assert [t.mode for t in storage.transactions.records] == ["read_write"]


@LEVEL7
def test_6b_supplementary_inserts_before_the_workers_task(world):
    s = world["s"]
    r, _ = runner(FakeRequestAuthorizer(), s)
    new = r.run(C.CreateSupplementaryTask(world["task"].id, "requirement_request", "Ask", "c"), world["worker"])
    assert new.id in s.tree.get(world["task"].id).depends_on


@LEVEL7
@pytest.mark.parametrize("command,principal", [
    (C.GetCurrentPrincipal(), ADMIN),
    (C.StartAdminSession("admin-pw"), None),
])
def test_command_bodies_run(command, principal):
    r, _ = runner(FakeRequestAuthorizer())
    assert r.run(command, principal) is not None


def test_routes_split_core_and_references():
    assert all(p.startswith(("/reader", "/references")) for _, p in REFERENCE_ROUTES)
    assert not any(p.startswith(("/reader", "/references")) for _, p in CORE_ROUTES)
