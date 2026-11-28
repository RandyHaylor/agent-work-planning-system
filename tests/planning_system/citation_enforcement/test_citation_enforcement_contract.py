"""Contract tests for citation_enforcement (spec: planning/05-spec-citation-enforcement-and-review.md,
tests 1-8), run against [fake, real]."""
import pytest

from planning_system.contract import Invalid
from planning_system.server.domain.citation_enforcement import CitationEnforcementService, ClaimPolicy
from planning_system.server.domain.citation_enforcement.fakes import FakeCitationEnforcement
from planning_system.server.domain.references.fakes import FakeReferenceLibrary, InMemoryReferenceStorage
from planning_system.server.domain.references.types import Reference

FIVE_LINES = "one\ntwo\nthree\nfour\nfive"


@pytest.fixture
def library():
    storage = InMemoryReferenceStorage()
    for ref_id, origin in [("ref-user", "user_exchange"), ("ref-reply", "proposal_response"),
                           ("ref-doc", "document"), ("ref-node", "node"), ("tmp-doc", "document")]:
        storage.save(Reference(ref_id, origin, FIVE_LINES, f"sha-{ref_id}"))
    storage.save(Reference("ref-old", "document", FIVE_LINES, "sha-old", superseded_by="ref-doc"))
    return FakeReferenceLibrary(storage)


@pytest.fixture(params=["fake", "real"])
def gate(request, library):
    if request.param == "fake":
        return FakeCitationEnforcement(library)
    return CitationEnforcementService(library)


def rejects(gate, text, tags, *fragments):
    with pytest.raises(Invalid) as error:
        gate.check_content(text, tags)
    for fragment in fragments:
        assert fragment in str(error.value), (fragment, str(error.value))
    return str(error.value)


# 1
@pytest.mark.parametrize("tags", [(), ("finding",), ("requirement", "technical")])
def test_1_exactly_one_claim_tag(gate, tags):
    rejects(gate, "x [ref-user:1-1]", tags, "exactly one claim tag",
            "requirement, decision, technical, documentation, plan, note, open_items")


def test_1b_other_descriptive_tags_may_sit_beside_the_claim_tag(gate):
    checked = gate.check_content("Use 72 hours [ref-user:2-3]", ("finding", "requirement"))
    assert checked.claim_tag == "requirement" and checked.citations[0].reference_id == "ref-user"


# 2
def test_2_requirement_needs_a_user_quote(gate):
    rejects(gate, "Use X [ref-doc:1-2]", ("requirement",), '"requirement"', "user_exchange or proposal_response",
            "Found only: document")
    assert gate.check_content("Use X [ref-user:1-2]", ("requirement",)).claim_tag == "requirement"
    assert gate.check_content("Use X [ref-reply:1-2]", ("decision",)).claim_tag == "decision"


# 3
def test_3_technical_and_documentation_need_reference_quotes(gate):
    rejects(gate, "It does X [ref-user:1-1]", ("technical",), "document or knowledge_base")
    assert gate.check_content("It does X [ref-doc:1-1] [ref-user:2-2]", ("technical",))
    rejects(gate, "Doc says X [ref-doc:1-1] [ref-user:1-1]", ("documentation",), "may cite only")
    assert gate.check_content("Doc says X [ref-doc:1-1]", ("documentation",))


# 4
def test_4_node_citations_alone_never_count(gate):
    for tag in ("requirement", "technical", "plan"):
        rejects(gate, "As decided [ref-node:1-1]", (tag,), "Found only: node")
    assert gate.check_content("As decided [ref-node:1-1] [ref-user:1-1]", ("requirement",))


# why rule (build log #60 (3), #61): plan and technical need a user citation (why) AND a document (proof)
@pytest.mark.parametrize("tag", ["plan", "technical"])
def test_why_rule_needs_both_a_user_and_a_document_citation(gate, tag):
    rejects(gate, "Use Postgres [ref-doc:1-1]", (tag,), f'a "{tag}" claim', "user quote",
            "user_exchange or proposal_response", "Found only: document")
    rejects(gate, "Use Postgres [ref-user:1-1]", (tag,), f'a "{tag}" claim', "document or knowledge_base",
                      "Found only: user_exchange")
    rejects(gate, "Use Postgres", (tag,), "user quote", "document or knowledge_base", "no citations")
    assert gate.check_content("Use Postgres [ref-user:1-1] [ref-doc:2-2]", (tag,)).claim_tag == tag
    assert gate.check_content("Use Postgres [ref-reply:1-1] [ref-doc:2-2]", (tag,)).claim_tag == tag


def test_why_rule_message_names_only_what_is_missing(gate):
    only_user_missing = rejects(gate, "Use Postgres [ref-doc:1-1]", ("plan",))
    assert "missing a user quote" in only_user_missing and "missing a reference quote" not in only_user_missing
    only_doc_missing = rejects(gate, "Use Postgres [ref-user:1-1]", ("plan",))
    assert "missing a reference quote" in only_doc_missing and "missing a user quote" not in only_doc_missing


def test_requirement_decision_documentation_unchanged_by_the_why_rule(gate):
    assert gate.check_content("Use X [ref-user:1-2]", ("requirement",))
    assert gate.check_content("Use X [ref-reply:1-2]", ("decision",))
    assert gate.check_content("Doc says X [ref-doc:1-1]", ("documentation",))


# open_items (build log #61 (4)): a to-do list of what to research or ask/verify with the user
def test_open_items_need_no_citation_and_are_not_reviewed(gate):
    checked = gate.check_content("RESEARCH: which queue library\nASK USER: retention period\n\n"
                                 "VERIFY WITH USER: in-app only for now", ("open_items",))
    assert checked.claim_tag == "open_items" and checked.citations == () and checked.reviewed is False
    assert gate.check_content("Use X [ref-user:1-2]", ("requirement",)).reviewed is True


@pytest.mark.parametrize("text", ["RESEARCH: x\nWe use Postgres", "research: lower case", "ASK USER x",
                                  "TODO: something", "  \n"])
def test_open_items_every_non_empty_line_needs_a_prefix(gate, text):
    message = rejects(gate, text, ("open_items",), '"open_items"', "RESEARCH:", "ASK USER:", "VERIFY WITH USER:")
    if text.strip():
        assert "line" in message


def test_open_items_may_still_carry_citations(gate):
    assert gate.check_content("VERIFY WITH USER: the 72 hours [ref-user:1-1]", ("open_items",))


def test_policy_from_config_keeps_flat_needs_working(library):
    table = {"plan": {"needs": ["user_exchange", "document"], "allowed": ["user_exchange", "document"]}}
    gate = CitationEnforcementService(library, ClaimPolicy.from_mapping(table))
    assert gate.check_content("x [ref-doc:1-1]", ("plan",)).reviewed is True


# 5
def test_5_bad_citations_are_all_reported_in_one_message(gate):
    message = rejects(gate, "x [ref-nope:1-1] [ref-old:1-1] [ref-user:0-3] [ref-user:5-2] [ref-user:4-9]",
                      ("requirement",), "ref-nope", "does not exist", "superseded by ref-doc", "cite ref-doc",
                      "0-3", "5-2", "4-9", "1-5")
    assert message.count(";") >= 4


def test_5b_unknown_temp_cache_id_says_cite_it_first(gate):
    rejects(gate, "x [tmp-unknown:1-1]", ("technical",), "tmp-unknown", "temp cache", "planning cite")


def test_5c_a_cited_temp_item_keeps_its_tmp_id_and_is_valid(gate):
    assert gate.check_content("x [tmp-doc:1-1]", ("documentation",))


# 6
def test_6_malformed_citation_like_text(gate):
    rejects(gate, "see [ref-x:12]", ("note",), 'malformed citation "[ref-x:12]"', "[reference-id:start-end]")


# 7
def test_7_note_needs_no_citation(gate):
    assert gate.check_content("Open question: which store?", ("note",)).citations == ()


# 8
@pytest.mark.parametrize("title", ["", "   ", "x" * 51, "cache [ref-doc:1-1]", "We use a cache.", "Why?"])
def test_8_bad_titles(gate, title):
    with pytest.raises(Invalid):
        gate.check_title(title)


def test_8b_good_title(gate):
    gate.check_title("vendor placement")
    gate.check_title("x" * 50)


def test_policy_from_config_can_add_a_tag(library):
    table = {"requirement": {"needs": ["user_exchange"], "allowed": ["user_exchange"], "hint": "needs a user quote"},
             "risk": {"needs": [], "allowed": ["document"]}}
    gate = CitationEnforcementService(library, ClaimPolicy.from_mapping(table))
    assert gate.check_content("maybe", ("risk",)).claim_tag == "risk"
    rejects(gate, "x", ("note",), "requirement, risk")
