"""In-process end to end: the REAL api_client through the REAL FastAPI app (TestClient transport), real
domain services, CommandRunner and RequestAuthorizer, over the in-memory stores. Walkthrough-1 style:
admin session -> project -> nodes -> planner -> assign (worker token) -> worker supplementary task ->
upload an HTML file into the reader -> toc/search/lines -> cite -> content citing it -> render ->
user exchange via the quote key -> context -> guidance -> revoke cascade -> end session."""
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from planning_system.api_client import ClientSettings
from planning_system.api_client.planning_api_client import PlanningApiClient
from planning_system.configuration import ConfigSection
from planning_system.contract import Forbidden, Invalid
from planning_system.server.adapters.fakes import FakeUploadedFileSource
from planning_system.server.composition import SourceFetcherByRequest, build_app, domain_settings
from planning_system.server.domain.authentication.fakes import InMemoryCredentialStorage
from planning_system.server.domain.authentication.password_hashing import PasswordHasher
from planning_system.server.domain.references.source_fetcher_port import UploadRequest
from planning_system.server.storage.fakes import InMemoryStorage, in_memory_stores

FIXTURE = Path(__file__).parent / "fixtures" / "caching_guide.html"
ADMIN_PASSWORD = "correct horse battery"
ROUTERS = [
    {"router": "planning_system.server.http_api.command_routes:router"},
    {"router": "planning_system.server.domain.references.http_routes:router"},
    {"router": "planning_system.prompt_builder.http_routes:router"},
]


class PbkdfCredentialStorage(InMemoryCredentialStorage):
    """The real AdminSessionService verifies a PBKDF2 hash (bootstrap stores one)."""

    def __init__(self):
        super().__init__()
        self._pbkdf = PasswordHasher(iterations=1_000).hash(ADMIN_PASSWORD)

    def admin_password_hash(self):
        return self._pbkdf


@pytest.fixture
def api():
    storage = InMemoryStorage(stores=replace(in_memory_stores(), credentials=PbkdfCredentialStorage()))
    section = ConfigSection("server", {"http_api": {"routers": ROUTERS}})
    settings = domain_settings(section, SourceFetcherByRequest({UploadRequest: FakeUploadedFileSource()}))
    client = TestClient(build_app(section, storage, settings), raise_server_exceptions=False)
    return PlanningApiClient(ClientSettings("http://testserver"), client._transport)


def test_walkthrough(api):
    # admin session (the popup posts the password)
    admin = api.with_token(api.start_admin_session(ADMIN_PASSWORD)["token"])
    assert admin.me()["role"] == "admin"
    with pytest.raises(Forbidden):
        api.start_admin_session("wrong")

    # project and the linear levels 2-4, then two tasks at level 5
    project = admin.create_project("Cache service", "We are building a caching service.")
    plan = admin.create_node(project["id"], "Plan", "high-level plan", "Plan the cache.")
    design = admin.create_node(plan["id"], "Design", "design", "Design the cache.")
    modules = admin.create_node(design["id"], "Modules", "module specs", "Specify the modules.")
    task = admin.create_node(modules["id"], "TTL purge", "build", "Purge expired entries at start.")
    later = admin.create_node(modules["id"], "Limits", "build", "Reject large bodies.")
    with pytest.raises(Invalid):
        admin.create_node(project["id"], "Second plan", "high-level plan", "levels 1-4 are linear")

    # planner for the project (admin mints it)
    planner_credential = admin.mint_credential("planner", project["id"], None, "planner-1")
    planner = api.with_token(planner_credential["token"])
    assert [n["id"] for n in planner.ready_children(modules["id"])] == [task["id"]]
    assert later["id"] not in [n["id"] for n in planner.ready_children(modules["id"])]

    # assign: node + worker token in one call
    assignment = planner.assign(task["id"], "worker-1", "feat/ttl")
    assert (assignment["node"]["assignee"], assignment["node"]["branch"]) == ("worker-1", "feat/ttl")
    worker = api.with_token(assignment["worker_token"])
    me = worker.me()
    assert (me["role"], me["scope_node_id"], me["agent_id"]) == ("worker", task["id"], "worker-1")
    with pytest.raises(Forbidden):
        worker.get_node(later["id"])

    # dev manager (build log #20): a planner may mint a planner in its own project
    assert planner.mint_credential("planner", project["id"], modules["id"], "dev-manager-1")["token"]

    # worker: supplementary task goes right before its own task and into its depends_on
    spike = worker.create_supplementary_task(task["id"], "tech_spike", "Check TTL config", "Where is TTL set?")
    assert spike["id"] in worker.get_node(task["id"])["depends_on"]
    assert "tech spike" in spike["labels"]

    # reader: upload a local HTML file, toc, search, lines
    [loaded] = worker.reader_load(file_path=FIXTURE)
    cache_id = loaded["cache_id"]
    assert loaded["strategy_used"] and loaded["metadata"]["origin_kind"] == "upload"
    assert isinstance(worker.reader_toc(cache_id)["toc"], list)
    hits = worker.reader_search("seventy", [cache_id])["results"]
    [(_, found)] = hits.items()
    line = found[0]["line_number"]
    assert "seventy two hours" in worker.reader_lines(cache_id, line, line)["text"]
    with pytest.raises(Forbidden):
        planner.reader_toc(cache_id)                      # another agent's temp cache

    # cite: the temp item moves into references keeping its id
    cited = worker.reader_cite(cache_id, line, line)
    assert cited["reference_id"] == cache_id
    assert cited["citation"] == f"[{cache_id}:{line}-{line}]"
    worker.add_content(task["id"], f"TTL is 72 hours {cited['citation']}", ["finding"])

    # the planner can read the reference because it can read a node that cites it
    rendered = planner.render_citation(cited["citation"])
    assert "seventy two hours" in rendered["text"]
    assert planner.get_reference(cache_id)["origin"] == "document"
    assert "seventy two hours" in planner.reference_lines(cache_id, line, line)["text"]

    # user exchange via the quote key; identical content reuses the stored copy
    quote = api.with_token(admin.mint_quote_key("laptop")["token"])
    first = quote.store_user_exchange("session-1", "Use 72 hours.", "How long should entries live?")
    again = quote.store_user_exchange("session-1", "Use 72 hours.", "How long should entries live?")
    assert first["reference_id"] == again["reference_id"]
    with pytest.raises(Forbidden):
        worker.store_user_exchange("s", "m", "p")

    # context for the worker's task: ancestors' summaries root first, then its own content
    context = worker.context(task["id"])
    assert context["context"].startswith("We are building a caching service.")
    assert "TTL is 72 hours" in context["context"]

    # guidance from the shipped prompt builder data
    guidance = worker.guidance("worker")
    assert guidance["role"] == "worker" and guidance["text"]

    # revoking the planner revokes the worker token it minted (cascade)
    admin.revoke_credential(planner_credential["credential_id"])
    with pytest.raises(Forbidden):
        worker.me()

    # ending the admin session
    assert admin.end_admin_session() == {"ended": True}
    with pytest.raises(Forbidden):
        admin.me()
