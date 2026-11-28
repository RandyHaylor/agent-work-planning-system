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
from planning_system.server.domain.references.ingestion.source_fetcher_port import UploadRequest
from planning_system.server.storage.fakes import InMemoryStorage, in_memory_stores

FIXTURE = Path(__file__).parent / "fixtures" / "caching_guide.html"
ADMIN_PASSWORD = "correct horse battery"
ROUTERS = [
    {"router": "planning_system.server.http_api.command_routes:router"},
    {"router": "planning_system.server.http_api.reference_routes:router"},
    {"router": "planning_system.server.http_api.guidance_routes:router"},
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

    def verdict(self, review_id, passed, reason, suggested_title=None, findings=()):
        return self._http.post(f"/reviews/{review_id}/verdict", headers=self._headers,
                               json={"passed": passed, "reason": reason, "suggested_title": suggested_title,
                                     "findings": list(findings)})


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
    added = worker.add_content(task["id"], f"TTL is 72 hours {cited['citation']}", ["finding", "documentation"])
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

    # spec 12: cited -> pending, listed; the node changed, so a whole-node guess screen opens too (#60 (5))
    added = worker.add_content(task["id"], f"Entries live 72 hours [{user_id}:2-2]", ["requirement"])
    assert added["review"]["status"] == "pending" and added["message"] == "submitted for review (not approved)"
    first_review = added["review"]["id"]
    first_node_review = added["node_review"]["id"]
    assert [r["id"] for r in reviews.list(project["id"], "pending").json()] == [first_review, first_node_review]

    # build log #61: open_items need no citation, open no content review, and are listed per project
    with pytest.raises(Invalid) as error:
        worker.add_content(task["id"], "RESEARCH: eviction policy\nWe use LRU", ["open_items"])
    assert "RESEARCH:" in str(error.value) and "ASK USER:" in str(error.value)
    todo = worker.add_content(task["id"], "RESEARCH: eviction policy\nASK USER: max entry size", ["open_items"])
    assert todo["review"] is None and "not reviewed" in todo["message"]
    node_review = todo["node_review"]["id"]                         # replaces the earlier node review
    assert [r["id"] for r in reviews.list(project["id"], "pending").json()] == [first_review, node_review]
    assert reviews.list(project["id"], "superseded").json()[0]["id"] == first_node_review
    [open_item] = planner.open_items(project["id"])
    assert (open_item["node_id"], open_item["reference_id"]) == (task["id"], todo["reference_id"])
    assert open_item["lines"] == ["RESEARCH: eviction policy", "ASK USER: max entry size"]

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
    assert packet["kind"] == "content"
    [citation] = packet["citations"]
    assert citation["quoted_text"] == "Use 72 hours."
    assert citation["pre_text"] == "How long should entries live?"
    # the whole-node packet: title, summary, every content item and all their quotes
    node_packet = reviewer.take(project["id"]).json()
    assert (node_packet["review_id"], node_packet["kind"]) == (node_review, "node")
    assert node_packet["node_title"] == "cache lifetime"
    assert [i["text"] for i in node_packet["content_items"]] == [
        f"Entries live 72 hours [{user_id}:2-2]", "RESEARCH: eviction policy\nASK USER: max entry size"]
    assert [c["quoted_text"] for c in node_packet["citations"]] == ["Use 72 hours."]
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
    # the guess screen fails too, with a reason per statement, shown the same way
    reviewer.verdict(node_review, False, "statement 1 guessed: 'entries' not in any reference")
    assert {r["id"] for r in reviews.list(project["id"], "failed").json()} == {first_review, node_review}

    # build log #50: can't be done with a failed review (content or whole node)
    with pytest.raises(Invalid) as error:
        planner.set_state(task["id"], "done")
    assert first_review in str(error.value) and node_review in str(error.value)

    # spec 15: replace -> old review superseded, new one pending; the failed node review is replaced too
    replaced = planner.replace_content(task["id"], added["reference_id"], f"Use 72 hours [{user_id}:2-2]")
    assert replaced["review"]["status"] == "pending"
    statuses = {r["id"]: r["status"] for r in reviews.list(project["id"]).json()}
    assert statuses == {first_review: "superseded", first_node_review: "superseded", node_review: "superseded",
                        replaced["review"]["id"]: "pending", replaced["node_review"]["id"]: "pending"}
    with pytest.raises(Invalid):
        planner.set_state(task["id"], "done")                       # still pending

    # a changed summary opens a new node review; an unchanged one does not
    planner.update_node(task["id"], context_summary="How long entries live.")
    assert len(reviews.list(project["id"], "pending").json()) == 2
    planner.update_node(task["id"], context_summary="How long cache entries live.")
    pending = [r["id"] for r in reviews.list(project["id"], "pending").json()]
    assert pending[0] == replaced["review"]["id"] and len(pending) == 2
    last_node_review = pending[1]

    # pass both -> done allowed
    assert reviewer.take(project["id"]).json()["review_id"] == replaced["review"]["id"]
    assert reviewer.verdict(replaced["review"]["id"], True, "quote states it").json()["status"] == "passed"
    with pytest.raises(Invalid):
        planner.set_state(task["id"], "done")                       # node review still pending
    assert reviewer.take(project["id"]).json()["review_id"] == last_node_review
    assert reviewer.verdict(last_node_review, True, "no guesses").json()["status"] == "passed"
    assert planner.set_state(task["id"], "done")["state"] == "done"


def _supersede_world(api, http):
    admin = api.with_token(api.start_admin_session(ADMIN_PASSWORD)["token"])
    project = admin.create_project("Cache service", "We are building a caching service.")
    parent = project
    for title, level in (("Plan", "high-level plan"), ("Design", "design"), ("Modules", "module specs")):
        parent = admin.create_node(parent["id"], title, level, f"{title} for the cache.")
    first = admin.create_node(parent["id"], "cache lifetime", "build", "How long entries live.")
    second = admin.create_node(parent["id"], "cache sizing", "build", "How big the cache is.")
    planner = api.with_token(admin.mint_credential("planner", project["id"], None, "planner-1")["token"])
    review_task = planner.create_node(parent["id"], "citation review", "build", "Review claims.", labels=["review"])
    reviewer = Reviews(http, planner.assign(review_task["id"], "reviewer-1", "main")["worker_token"])
    planner.set_state(review_task["id"], "in_progress")
    quote = api.with_token(admin.mint_quote_key("laptop")["token"])
    return admin, planner, reviewer, quote, project, first, second


def _decide_all(reviewer, project_id, decide):
    """Takes every pending review; decide(packet) -> (passed, reason, findings)."""
    decided = []
    while True:
        taken = reviewer.take(project_id)
        if taken.status_code == 204:
            return decided
        packet = taken.json()
        passed, reason, findings = decide(packet)
        assert reviewer.verdict(packet["review_id"], passed, reason, None, findings).status_code == 200
        decided.append(packet)


def test_user_quote_supersede_check_trial_request_and_confirm(api, http):
    """05-spec-reference-supersede.md: a new user quote is checked against ALL cited user quotes in ONE review;
    a change -> a candidate (never automatic) -> a trial review of every item citing the old quote -> a
    requirement request before the earliest affected task -> only the user (admin) confirms -> superseded, and
    the citing items' reviews reopen against the new version."""
    admin, planner, reviewer, quote, project, first, second = _supersede_world(api, http)
    old = quote.store_user_exchange("s-1", "Use 72 hours.", "How long should entries live?")["reference_id"]
    planner.add_content(first["id"], f"Entries live 72 hours [{old}:2-2]", ["requirement"])
    assert all(p["kind"] in ("content", "node") for p in _decide_all(reviewer, project["id"],
                                                                         lambda p: (True, "ok", [])))
    new = quote.store_user_exchange("s-1", "Make it 24 hours.", "Is 72 hours still right?")["reference_id"]
    planner.add_content(second["id"], f"Cache size is 24 hours of entries [{new}:2-2]", ["requirement"])

    def judge(packet):
        if packet["kind"] == "quote_check":
            assert packet["subject"]["quoted_text"] == "Make it 24 hours."
            assert [c["quoted_text"] for c in packet["citations"]] == ["Use 72 hours."]
            [candidates_before] = [planner.supersede_candidates(project["id"])]
            assert candidates_before == []
            return False, "replaces 72 hours with 24", [old]
        if packet["kind"] == "trial":
            [proposed] = planner.supersede_candidates(project["id"], "proposed")
            assert (proposed["kind"], proposed["found_by"]) == ("user_quote", "quote_check")
            assert planner.get_reference(old).get("superseded_note") is None      # nothing changed yet
            assert "Make it 24 hours." in packet["against_text"]
            assert packet["comparisons"][0]["old_text"] == "Use 72 hours."
            return False, "the new quote says 24 hours", []
        return True, "ok", []
    kinds = [p["kind"] for p in _decide_all(reviewer, project["id"], judge)]
    assert kinds.index("quote_check") < kinds.index("trial")
    [candidate] = planner.supersede_candidates(project["id"], "trial_reviewed")
    request = planner.get_node(candidate["request_node_id"])
    assert "requirement request" in request["labels"] and request["parent_id"] == first["parent_id"]
    assert request["id"] in planner.get_node(first["id"])["depends_on"]
    assert candidate["id"] in request["context_summary"]
    context = planner.context(request["id"])["context"]
    assert "Discrepancy" in context and "the new quote says 24 hours" in context

    with pytest.raises(Forbidden):
        planner.confirm_supersede(candidate["id"])                            # user quotes: the user only
    confirmed = admin.confirm_supersede(candidate["id"])
    assert confirmed["candidate"]["status"] == "confirmed" and len(confirmed["reopened_review_ids"]) == 1
    assert planner.get_reference(old)["superseded_note"]
    reopened = reviewer.take(project["id"]).json()
    assert reopened["review_id"] == confirmed["reopened_review_ids"][0]
    assert "Make it 24 hours." in reopened["citations"][0]["quoted_text"]
    with pytest.raises(Invalid):
        planner.set_state(first["id"], "done")                                # reopened review pending


def test_document_reload_candidate_search_and_reject(api, http, tmp_path):
    """Same file loaded again with other content -> a candidate (never automatic); the load response lists the
    stored copy (search first); the planner may reject a document candidate, and the pair stays rejected."""
    admin, planner, reviewer, quote, project, first, second = _supersede_world(api, http)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "guide.txt").write_text("Cache guide\nEntries expire after seventy two hours.\n")
    (tmp_path / "b" / "guide.txt").write_text("Cache guide\nEntries expire after one day.\nDeprecated: TTL.\n")
    [loaded] = planner.reader_load(file_path=tmp_path / "a" / "guide.txt")
    cited = planner.reader_cite(loaded["cache_id"], 2, 2)
    planner.add_content(second["id"], f"The guide says entries expire after 72 hours {cited['citation']}",
                        ["documentation"])
    assert [r["id"] for r in planner.search_references("seventy hours")] == [cited["reference_id"]]
    [again] = planner.reader_load(file_path=tmp_path / "b" / "guide.txt")
    assert [r["id"] for r in again["related_references"]["same_source"]] == [cited["reference_id"]]
    assert planner.supersede_candidates(project["id"]) == []                  # loading alone proposes nothing
    newer = planner.reader_cite(again["cache_id"], 2, 2)
    [candidate] = planner.supersede_candidates(project["id"])
    assert (candidate["old_reference_id"], candidate["new_reference_id"], candidate["kind"], candidate["found_by"]) \
        == (cited["reference_id"], newer["reference_id"], "document", "same_source")
    trials = [p for p in _decide_all(reviewer, project["id"], lambda p: (True, "ok", [])) if p["kind"] == "trial"]
    assert len(trials) == 1 and trials[0]["comparisons"][0]["new_text"].startswith("Entries expire after one day.")
    assert "Deprecated: TTL." in trials[0]["against_text"]                   # the whole newer copy too
    rejected = planner.reject_supersede(candidate["id"], "the old page was right for our version")
    assert (rejected["status"], rejected["reason"]) == ("rejected", "the old page was right for our version")
    assert planner.propose_supersede(project["id"], cited["reference_id"], newer["reference_id"])["status"] == \
        "rejected"
    assert planner.get_reference(cited["reference_id"]).get("superseded_note") is None
