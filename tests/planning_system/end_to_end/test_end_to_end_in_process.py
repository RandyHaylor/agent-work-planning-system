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
def http():
    storage = InMemoryStorage(stores=replace(in_memory_stores(), credentials=PbkdfCredentialStorage()))
    section = ConfigSection("server", {"http_api": {"routers": ROUTERS}})
    settings = domain_settings(section, SourceFetcherByRequest({UploadRequest: FakeUploadedFileSource()}))
    return TestClient(build_app(section, storage, settings), raise_server_exceptions=False)


@pytest.fixture
def api(http):
    return PlanningApiClient(ClientSettings("http://testserver"), http._transport)


class Reviews:
    """The /reviews routes over raw HTTP (the api_client's review methods are built by the client side)."""

    def __init__(self, http, token):
        self._http, self._headers = http, {"Authorization": f"Bearer {token}"}

    def list(self, project_id, status=None):
        params = {"project_id": project_id, **({"status": status} if status else {})}
        return self._http.get("/reviews", params=params, headers=self._headers)

    def take(self, project_id):
        return self._http.post("/reviews/take", json={"project_id": project_id}, headers=self._headers)

    def verdict(self, review_id, passed, reason, suggested_title=None):
        return self._http.post(f"/reviews/{review_id}/verdict", headers=self._headers,
                               json={"passed": passed, "reason": reason, "suggested_title": suggested_title})


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
    with pytest.raises(Invalid):
        worker.add_content(task["id"], f"TTL is 72 hours {cited['citation']}", ["finding"])   # no claim tag
    added = worker.add_content(task["id"], f"TTL is 72 hours {cited['citation']}", ["finding", "technical"])
    assert added["review"]["status"] == "pending" and "not approved" in added["message"]

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


def test_citation_gate_and_content_review(api, http):
    """Spec tests 11-16 + build log #50: no citation -> 422; cited -> review pending -> taken by the
    review-task worker -> fail -> planner sees it -> node can't be done -> replace -> pass -> done."""
    admin_token = api.start_admin_session(ADMIN_PASSWORD)["token"]
    admin = api.with_token(admin_token)
    project = admin.create_project("Cache service", "We are building a caching service.")
    plan = admin.create_node(project["id"], "Plan", "high-level plan", "Plan the cache.")
    design = admin.create_node(plan["id"], "Design", "design", "Design the cache.")
    modules = admin.create_node(design["id"], "Modules", "module specs", "Specify the modules.")
    task = admin.create_node(modules["id"], "cache lifetime", "build", "How long entries live.")
    planner_token = admin.mint_credential("planner", project["id"], None, "planner-1")["token"]
    planner = api.with_token(planner_token)
    worker_token = planner.assign(task["id"], "worker-1", "feat/ttl")["worker_token"]
    worker = api.with_token(worker_token)

    # titles make no claims (spec 16)
    for bad in ("Entries live 72 hours.", "x" * 51, ""):
        with pytest.raises(Invalid):
            planner.create_node(modules["id"], bad, "build", "c")
    with pytest.raises(Invalid):
        planner.update_node(task["id"], title="ttl [ref-x:1-1]")
    with pytest.raises(Invalid):
        worker.create_supplementary_task(task["id"], "requirement_request", "Which TTL?", "Ask the user.")

    # the user's words, via the quote key
    quote = api.with_token(admin.mint_quote_key("laptop")["token"])
    user = quote.store_user_exchange("s-1", "Use 72 hours.", "How long should entries live?")
    user_id = user["reference_id"]

    # spec 11: no citation -> 422 saying what to add; nothing stored, no review record
    with pytest.raises(Invalid) as error:
        worker.add_content(task["id"], "Entries live 72 hours", ["requirement"])
    assert "needs a user quote" in str(error.value)
    with pytest.raises(Invalid) as error:
        worker.add_content(task["id"], f"Entries live 72 hours [{user_id}:2-9]", ["requirement"])
    assert "has 2 lines" in str(error.value)
    assert "Entries live" not in worker.context(task["id"])["context"]
    reviews = Reviews(http, planner_token)
    assert reviews.list(project["id"]).json() == []

    # spec 12: cited -> pending, listed
    added = worker.add_content(task["id"], f"Entries live 72 hours [{user_id}:2-2]", ["requirement"])
    assert added["review"]["status"] == "pending" and added["message"] == "submitted for review (not approved)"
    first_review = added["review"]["id"]
    assert [r["id"] for r in reviews.list(project["id"], "pending").json()] == [first_review]

    # the planner starts the standing review task (a worker on a task labelled "review")
    review_task = planner.create_node(modules["id"], "citation review", "build", "Review cited claims.",
                                      labels=["review"])
    reviewer_token = planner.assign(review_task["id"], "reviewer-1", "main")["worker_token"]
    reviewer = Reviews(http, reviewer_token)
    assert reviewer.take(project["id"]).status_code == 403          # task not started yet
    planner.set_state(review_task["id"], "in_progress")

    # spec 13: a worker not on a review task -> 403; the review-task worker -> packet; empty -> 204
    assert Reviews(http, worker_token).take(project["id"]).status_code == 403
    taken = reviewer.take(project["id"])
    assert taken.status_code == 200, taken.text
    packet = taken.json()
    assert packet["review_id"] == first_review and packet["claim_tag"] == "requirement"
    [citation] = packet["citations"]
    assert citation["quoted_text"] == "Use 72 hours."
    assert citation["pre_text"] == "How long should entries live?"
    assert reviewer.take(project["id"]).status_code == 204
    # build log #50: the holder may read the quotes of the review it holds
    holder = api.with_token(reviewer_token)
    assert "Use 72 hours." in holder.render_citation(f"[{user_id}:2-2]")["text"]

    # only the holder decides
    assert Reviews(http, admin_token).verdict(first_review, True, "ok").status_code == 409

    # spec 14: fail -> the planner sees reason + suggested title; node state unchanged
    failed = reviewer.verdict(first_review, False, "quote does not mention entries", "entry lifetime")
    assert failed.status_code == 200 and failed.json()["status"] == "failed"
    [seen] = reviews.list(project["id"], "failed").json()
    assert (seen["reason"], seen["suggested_title"]) == ("quote does not mention entries", "entry lifetime")
    assert planner.get_node(task["id"])["state"] == "assigned"

    # build log #50: can't be done with a failed review
    with pytest.raises(Invalid) as error:
        planner.set_state(task["id"], "done")
    assert first_review in str(error.value)

    # spec 15: replace -> old review superseded, new one pending
    replaced = planner.replace_content(task["id"], added["reference_id"], f"Use 72 hours [{user_id}:2-2]")
    assert replaced["review"]["status"] == "pending"
    statuses = {r["id"]: r["status"] for r in reviews.list(project["id"]).json()}
    assert statuses == {first_review: "superseded", replaced["review"]["id"]: "pending"}
    with pytest.raises(Invalid):
        planner.set_state(task["id"], "done")                       # still pending

    # pass -> done allowed
    assert reviewer.take(project["id"]).json()["review_id"] == replaced["review"]["id"]
    assert reviewer.verdict(replaced["review"]["id"], True, "quote states it").json()["status"] == "passed"
    assert planner.set_state(task["id"], "done")["state"] == "done"
