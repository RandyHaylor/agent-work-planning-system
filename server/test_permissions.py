"""Unit tests for the isolated permissions module. Pure, no IO."""
from server import permissions as P

# Tree:  1(root) -> 2(kb) -> 5
#                -> 3(plans) -> 4 -> 6
#                -> 7
PARENT = {1: None, 2: 1, 3: 1, 4: 3, 5: 2, 6: 4, 7: 1}


def anc(n):
    out = []
    while n is not None:
        out.append(n)
        n = PARENT[n]
    return out


KB = 2
root = P.Principal(token_id=1, scope_node_id=1, role=P.PLANNER, is_root=True)
planner = P.Principal(token_id=2, scope_node_id=3, role=P.PLANNER)
worker = P.Principal(token_id=3, scope_node_id=4, role=P.WORKER)


def test_worker_reads_scope_and_descendants_only():
    assert P.can_read(worker, 4, anc, KB)
    assert P.can_read(worker, 6, anc, KB)
    assert not P.can_read(worker, 3, anc, KB)
    assert not P.can_read(worker, 1, anc, KB)
    assert not P.can_read(worker, 7, anc, KB)


def test_planner_reads_everything():
    for n in PARENT:
        assert P.can_read(planner, n, anc, KB), n


def test_kb_readable_by_everyone():
    assert P.can_read(worker, 5, anc, KB)
    assert P.can_read(planner, 5, anc, KB)


def test_kb_writable_by_any_planner_not_workers():
    assert P.can_write_doc(root, 5, "summary", anc, KB)
    assert P.can_write_doc(planner, 5, "instruction", anc, KB)
    assert P.can_create_child(planner, 2, anc, KB)
    assert P.can_create_child(root, 2, anc, KB)
    assert P.can_edit_doc(planner, 5, "summary", 99, anc, KB)
    assert not P.can_write_doc(worker, 5, "report", anc, KB)
    assert not P.can_create_child(worker, 2, anc, KB)
    assert not P.can_edit_doc(worker, 5, "report", worker.token_id, anc, KB)


def test_create_child_in_scope_only():
    assert P.can_create_child(worker, 4, anc, KB)
    assert P.can_create_child(worker, 6, anc, KB)
    assert not P.can_create_child(worker, 3, anc, KB)
    assert P.can_create_child(planner, 4, anc, KB)


def test_planner_writes_every_role_in_scope():
    for role in ("summary", "instruction", "environment", "question", "survey", "approval", "review",
                 "report", "spike", "escalation", "kb_proposal"):
        assert P.can_write_doc(planner, 4, role, anc, KB), role
    assert not P.can_write_doc(planner, 7, "question", anc, KB)


def test_worker_writes_only_worker_roles_in_scope():
    for role in ("report", "spike", "escalation", "kb_proposal"):
        assert P.can_write_doc(worker, 4, role, anc, KB), role
        assert P.can_write_doc(worker, 6, role, anc, KB), role
        assert not P.can_write_doc(worker, 3, role, anc, KB), role
    for role in ("summary", "instruction", "environment", "question", "survey", "approval", "review"):
        assert not P.can_write_doc(worker, 4, role, anc, KB), role
        assert not P.can_write_doc(worker, 6, role, anc, KB), role


def test_edit_rules():
    assert P.can_edit_doc(worker, 4, "report", worker.token_id, anc, KB)
    assert P.can_edit_doc(worker, 6, "summary", worker.token_id, anc, KB)  # summary of a node it created
    assert not P.can_edit_doc(worker, 4, "report", planner.token_id, anc, KB)
    assert not P.can_edit_doc(worker, 4, "instruction", planner.token_id, anc, KB)
    assert not P.can_edit_doc(worker, 3, "report", worker.token_id, anc, KB)  # out of scope
    assert P.can_edit_doc(planner, 4, "report", worker.token_id, anc, KB)
    assert P.can_edit_doc(planner, 4, "instruction", root.token_id, anc, KB)
    assert not P.can_edit_doc(planner, 7, "report", planner.token_id, anc, KB)


def test_state_planner_only():
    assert P.can_set_state(planner, 4, anc, KB)
    assert P.can_set_state(planner, 6, anc, KB)
    assert not P.can_set_state(worker, 4, anc, KB)
    assert not P.can_set_state(worker, 6, anc, KB)
    assert not P.can_set_state(planner, 7, anc, KB)


def test_answer_escalation_planner_only():
    assert P.can_answer_escalation(planner, 6, anc)
    assert not P.can_answer_escalation(worker, 6, anc)
    assert not P.can_answer_escalation(planner, 7, anc)


def test_mint():
    assert P.can_mint(planner, 4, P.WORKER, anc)
    assert P.can_mint(planner, 6, P.PLANNER, anc)
    assert not P.can_mint(worker, 6, P.WORKER, anc)
    assert not P.can_mint(planner, 7, P.WORKER, anc)
    assert not P.can_mint(planner, 4, "admin", anc)


def test_revoke_any_planner_whose_scope_contains_token_scope():
    assert P.can_revoke(planner, 4, anc)
    assert P.can_revoke(planner, 6, anc)
    assert P.can_revoke(root, 6, anc)
    assert not P.can_revoke(planner, 7, anc)
    assert not P.can_revoke(worker, 6, anc)


def test_list_tokens_planner_only():
    assert P.can_list_tokens(planner)
    assert not P.can_list_tokens(worker)
