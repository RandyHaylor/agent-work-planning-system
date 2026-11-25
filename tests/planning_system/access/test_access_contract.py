"""Contract tests for access (spec: planning/05-spec-access.md). Pure; no mocks needed."""
import pytest

from planning_system.contract import Principal
from planning_system.server.domain.access.fakes import TablePermissionPolicy
from planning_system.server.domain.access.permission_policy import RulePermissionPolicy
from planning_system.server.domain.access.types import (CredentialScope, KnowledgeBaseFacts,
                                                        NodeFacts, ReferenceFacts, TempEntryFacts)

@pytest.fixture(params=["fake", "real"])
def policy(request):
    return TablePermissionPolicy() if request.param == "fake" else RulePermissionPolicy()


PROJECT, OTHER_PROJECT = 1, 100
ROOT = NodeFacts(1, PROJECT)
PARENT = NodeFacts(3, PROJECT)
TASK = NodeFacts(5, PROJECT, assignee="w1")
SIBLING = NodeFacts(6, PROJECT, assignee="w2")
FOREIGN = NodeFacts(101, OTHER_PROJECT)
REQUEST = NodeFacts(7, PROJECT, assignee="w1")

ADMIN = Principal(None, "admin")
PLANNER = Principal("p1", "planner", PROJECT, PROJECT)
WORKER = Principal("w1", "worker", PROJECT, TASK.node_id)
QUOTE = Principal(None, "quote_client")


def every_rule(policy, p):
    """Every rule, with the facts used for the 'can do everything / nothing else' tests."""
    return {
        "read_node": policy.can_read_node(p, FOREIGN, (NodeFacts(100, OTHER_PROJECT),)),
        "read_reference": policy.can_read_reference(p, ReferenceFacts("r1"), (FOREIGN,)),
        "read_temp_entry": policy.can_read_temp_entry(p, TempEntryFacts("c1", "someone")),
        "read_knowledge_base": policy.can_read_knowledge_base(p, KnowledgeBaseFacts(9)),
        "create_node": policy.can_create_node(p, FOREIGN),
        "edit_node": policy.can_edit_node(p, FOREIGN),
        "set_state": policy.can_set_state(p, FOREIGN, "done"),
        "assign": policy.can_assign(p, FOREIGN),
        "create_supplementary_task": policy.can_create_supplementary_task(p, FOREIGN),
        "answer_requirement_request": policy.can_answer_requirement_request(p, FOREIGN),
        "add_content": policy.can_add_content(p, FOREIGN),
        "store_proposal_response": policy.can_store_proposal_response(p),
        "mint": policy.can_mint(p, CredentialScope("worker", OTHER_PROJECT, 101), "worker"),
        "revoke": policy.can_revoke(p, CredentialScope("worker", OTHER_PROJECT, 101)),
        "rotate": policy.can_rotate(p, CredentialScope("worker", OTHER_PROJECT, 101)),
    }


def test_1_worker_reads_only_its_own_task(policy):
    assert policy.can_read_node(WORKER, TASK, (ROOT, PARENT))
    for other in (ROOT, PARENT, SIBLING, FOREIGN):
        assert not policy.can_read_node(WORKER, other, ())


def test_2_worker_cannot_edit_any_node(policy):
    for node in (TASK, PARENT, SIBLING, FOREIGN):
        assert not policy.can_edit_node(WORKER, node)


def test_3_worker_creates_supplementary_task_only_for_its_own_task(policy):
    assert policy.can_create_supplementary_task(WORKER, TASK)
    assert not policy.can_create_supplementary_task(WORKER, SIBLING)
    assert not policy.can_create_supplementary_task(WORKER, FOREIGN)


def test_4_only_the_assignee_answers_a_requirement_request(policy):
    assert policy.can_answer_requirement_request(WORKER, REQUEST)
    assert not policy.can_answer_requirement_request(Principal("w2", "worker", PROJECT, 6), REQUEST)
    assert not policy.can_answer_requirement_request(QUOTE, REQUEST)


def test_5_temp_entry_readable_by_fetcher_and_admin_only(policy):
    entry = TempEntryFacts("c1", "w1")
    assert policy.can_read_temp_entry(WORKER, entry)
    assert policy.can_read_temp_entry(ADMIN, entry)
    assert not policy.can_read_temp_entry(PLANNER, entry)
    assert not policy.can_read_temp_entry(Principal("w2", "worker", PROJECT, 6), entry)


def test_6_cited_reference_readable_by_anyone_who_reads_a_citing_node(policy):
    ref = ReferenceFacts("r1")
    assert policy.can_read_reference(WORKER, ref, (SIBLING, TASK))
    assert not policy.can_read_reference(WORKER, ref, (SIBLING,))
    assert policy.can_read_reference(PLANNER, ref, (SIBLING,))
    assert not policy.can_read_reference(PLANNER, ref, (FOREIGN,))


def test_7_quote_key_submits_user_quotes_and_nothing_else(policy):
    assert policy.can_submit_user_quote(QUOTE)
    for p in (ADMIN, PLANNER, WORKER):
        assert not policy.can_submit_user_quote(p)
    assert not any(every_rule(policy, QUOTE).values())
    assert not policy.can_read_node(QUOTE, TASK, ())
    assert not policy.can_create_node(QUOTE, TASK)


def test_8_planner_acts_only_inside_its_own_project(policy):
    assert policy.can_create_node(PLANNER, PARENT)
    assert policy.can_edit_node(PLANNER, TASK)
    assert policy.can_assign(PLANNER, TASK)
    assert policy.can_set_state(PLANNER, TASK, "done")
    assert not policy.can_create_node(PLANNER, FOREIGN)
    assert not policy.can_edit_node(PLANNER, FOREIGN)
    assert not policy.can_assign(PLANNER, FOREIGN)
    assert not policy.can_set_state(PLANNER, FOREIGN, "done")


def test_8b_planner_mints_workers_and_dev_manager_planners_in_its_project_only(policy):
    # decision #20: a planner may mint a planner token scoped to a node inside its own project
    assert policy.can_mint(PLANNER, CredentialScope("worker", PROJECT, TASK.node_id), "worker")
    assert policy.can_mint(PLANNER, CredentialScope("planner", PROJECT, PARENT.node_id), "planner")
    assert not policy.can_mint(PLANNER, CredentialScope("planner", OTHER_PROJECT, 101), "planner")
    assert not policy.can_mint(PLANNER, CredentialScope("quote_client"), "quote_client")
    assert not policy.can_mint(WORKER, CredentialScope("worker", PROJECT, TASK.node_id), "worker")


def test_9_admin_can_do_everything(policy):
    rules = every_rule(policy, ADMIN)
    assert all(rules.values()), [k for k, v in rules.items() if not v]


def test_10_revoking_a_planner_revokes_the_worker_tokens_it_minted(policy):
    """The rule side: whoever may revoke the planner's token; the cascade itself is authentication's
    (tests/planning_system/authentication test 3), exercised here through the authentication fake."""
    from planning_system.server.domain.authentication.fakes import (FakeAuthentication, FakeClock,
                                                                    InMemoryCredentialStorage)
    assert policy.can_revoke(ADMIN, CredentialScope("planner", PROJECT, PROJECT))
    auth = FakeAuthentication(InMemoryCredentialStorage(), policy, FakeClock())
    planner = auth.mint(ADMIN, "planner", PROJECT, PROJECT, "p1")
    worker = auth.mint(planner.principal, "worker", PROJECT, TASK.node_id, "w1")
    auth.revoke(ADMIN, planner.credential_id)
    with pytest.raises(Exception):
        auth.authenticate(worker.token)


def test_can_review_admin_planner_or_worker_on_an_in_progress_review_task(policy):
    review_task = NodeFacts(TASK.node_id, PROJECT, "w1", frozenset({"review"}), "in_progress")
    assert policy.can_review(ADMIN, OTHER_PROJECT, None)
    assert policy.can_review(PLANNER, PROJECT, None)
    assert not policy.can_review(PLANNER, OTHER_PROJECT, None)
    assert policy.can_review(WORKER, PROJECT, review_task)
    assert not policy.can_review(WORKER, OTHER_PROJECT, review_task)
    assert not policy.can_review(WORKER, PROJECT, TASK)                                   # not labelled review
    assert not policy.can_review(WORKER, PROJECT, NodeFacts(TASK.node_id, PROJECT, "w1", frozenset({"review"}),
                                                            "assigned"))                 # not started
    assert not policy.can_review(WORKER, PROJECT, NodeFacts(SIBLING.node_id, PROJECT, "w2", frozenset({"review"}),
                                                            "in_progress"))              # not its own task
    assert not policy.can_review(QUOTE, PROJECT, None)
