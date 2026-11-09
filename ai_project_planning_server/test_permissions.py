"""Unit tests for the isolated permissions module. Pure, no IO."""
from ai_project_planning_server import permissions as P

# Tree:  1(root) -> 2(kb) -> 8(kb Product) -> 9
#                         -> 10(kb Company)
#                -> 3(plans) -> 4(workorder A) -> 6
#                            -> 7(workorder B, hidden) -> 11
#                            -> 12(workorder C, visible)
PARENT = {1: None, 2: 1, 3: 1, 4: 3, 6: 4, 7: 3, 8: 2, 9: 8, 10: 2, 11: 7, 12: 3}


def anc(n):
    out = []
    while n is not None:
        out.append(n)
        n = PARENT[n]
    return out


V = P.View(root=1, plans=3, kb=2, readable_workorders=frozenset({4, 12}), readable_kbs=frozenset({8}))
admin = P.Principal(token_id=None, scope_node_id=1, role=P.ADMIN)
planner = P.Principal(token_id=2, scope_node_id=4, role=P.PLANNER, workorder_id=4)
worker = P.Principal(token_id=3, scope_node_id=6, role=P.WORKER, workorder_id=4)
access = P.Principal(token_id=None, scope_node_id=1, role=P.ACCESS)


def test_access_only_creates_workorders_and_nothing_else():
    assert P.can_create_workorder(access) and P.can_create_workorder(None)
    assert P.can_create_workorder(planner) and P.can_create_workorder(admin)
    assert not P.can_create_workorder(worker)
    for n in PARENT:
        assert not P.can_read(access, n, anc, V), n
        assert not P.can_create_child(access, n, anc, V), n
        assert not P.can_write_doc(access, n, "report", anc, V), n
        assert not P.can_edit_doc(access, n, "report", None, anc, V), n
        assert not P.can_set_state(access, n, anc, V), n
    assert not P.can_mint(access, 4, P.WORKER, anc, V)


def test_kb_selection_and_visibility_rights():
    assert P.can_assign_kbs(planner, 4) and not P.can_assign_kbs(planner, 12)
    assert P.can_assign_kbs(admin, 12)
    assert not P.can_assign_kbs(worker, 4)
    assert P.can_set_visibility(admin)
    assert not P.can_set_visibility(planner) and not P.can_set_visibility(worker)


def test_workorder_of_and_kb_of():
    assert P.workorder_of(6, anc, 3) == 4
    assert P.workorder_of(4, anc, 3) == 4
    assert P.workorder_of(3, anc, 3) is None
    assert P.workorder_of(9, anc, 3) is None
    assert P.kb_of(9, anc, 2) == 8
    assert P.kb_of(2, anc, 2) is None


def test_admin_reads_and_writes_everything():
    for n in PARENT:
        assert P.can_read(admin, n, anc, V), n
        assert P.can_create_child(admin, n, anc, V), n
        assert P.can_set_state(admin, n, anc, V), n
        for role in P.ALL_DOC_ROLES:
            assert P.can_write_doc(admin, n, role, anc, V), (n, role)
        assert P.can_edit_doc(admin, n, "report", 99, anc, V), n


def test_planner_reads_own_visible_and_granted_workorders_not_hidden():
    assert P.can_read(planner, 4, anc, V) and P.can_read(planner, 6, anc, V)
    assert P.can_read(planner, 12, anc, V)
    assert not P.can_read(planner, 7, anc, V) and not P.can_read(planner, 11, anc, V)
    assert P.can_read(planner, 1, anc, V) and P.can_read(planner, 3, anc, V) and P.can_read(planner, 2, anc, V)


def test_planner_reads_every_kb_worker_only_selected():
    for n in (2, 8, 9, 10):
        assert P.can_read(planner, n, anc, V), n
    assert P.can_read(worker, 8, anc, V) and P.can_read(worker, 9, anc, V)
    assert not P.can_read(worker, 10, anc, V)
    assert not P.can_read(worker, 2, anc, V)


def test_worker_reads_scope_subtree_only():
    assert P.can_read(worker, 6, anc, V)
    for n in (4, 3, 1, 12, 7, 11):
        assert not P.can_read(worker, n, anc, V), n


def test_nobody_but_admin_writes_kb():
    for n in (2, 8, 9, 10):
        for who in (planner, worker):
            assert not P.can_write_doc(who, n, "summary", anc, V), n
            assert not P.can_write_doc(who, n, "report", anc, V), n
            assert not P.can_create_child(who, n, anc, V), n
            assert not P.can_edit_doc(who, n, "summary", who.token_id, anc, V), n
            assert not P.can_set_state(who, n, anc, V), n


def test_planner_writes_only_in_own_workorder():
    for role in P.ALL_DOC_ROLES:
        assert P.can_write_doc(planner, 4, role, anc, V), role
        assert P.can_write_doc(planner, 6, role, anc, V), role
        assert not P.can_write_doc(planner, 12, role, anc, V), role
    assert P.can_create_child(planner, 6, anc, V)
    assert not P.can_create_child(planner, 12, anc, V)
    assert not P.can_create_child(planner, 3, anc, V)  # cannot create workorders
    assert P.can_set_state(planner, 6, anc, V) and not P.can_set_state(planner, 12, anc, V)
    assert P.can_edit_doc(planner, 6, "report", worker.token_id, anc, V)
    assert not P.can_edit_doc(planner, 12, "report", 99, anc, V)


def test_worker_writes_worker_roles_in_scope_edits_own():
    for role in P.WORKER_DOC_ROLES:
        assert P.can_write_doc(worker, 6, role, anc, V), role
    for role in P.PLANNER_ONLY_DOC_ROLES:
        assert not P.can_write_doc(worker, 6, role, anc, V), role
    assert not P.can_write_doc(worker, 4, "report", anc, V)
    assert P.can_create_child(worker, 6, anc, V) and not P.can_create_child(worker, 4, anc, V)
    assert P.can_edit_doc(worker, 6, "report", worker.token_id, anc, V)
    assert not P.can_edit_doc(worker, 6, "instruction", planner.token_id, anc, V)
    assert not P.can_set_state(worker, 6, anc, V)


def test_answer_and_resolve():
    assert P.can_answer_escalation(planner, 6, anc, V)
    assert not P.can_answer_escalation(planner, 11, anc, V)
    assert not P.can_answer_escalation(worker, 6, anc, V)
    assert P.can_answer_escalation(admin, 11, anc, V)
    assert P.can_resolve_proposal(admin)
    assert not P.can_resolve_proposal(planner) and not P.can_resolve_proposal(worker)


def test_mint():
    assert P.can_mint(planner, 6, P.WORKER, anc, V)
    assert not P.can_mint(planner, 6, P.PLANNER, anc, V)
    assert not P.can_mint(planner, 11, P.WORKER, anc, V)
    assert not P.can_mint(planner, 4, P.ADMIN, anc, V)
    assert not P.can_mint(worker, 6, P.WORKER, anc, V)
    assert P.can_mint(admin, 4, P.PLANNER, anc, V) and P.can_mint(admin, 11, P.WORKER, anc, V)
    assert not P.can_mint(admin, 3, P.PLANNER, anc, V)  # a planner needs a workorder
    assert not P.can_mint(admin, 6, P.PLANNER, anc, V)  # and is scoped to the workorder node itself, never inside it
    assert P.planner_scope_ok(4, anc, V) and not P.planner_scope_ok(6, anc, V) and not P.planner_scope_ok(3, anc, V)
    # the admin is a session, never a token: nobody mints one
    assert not P.can_mint(admin, 1, P.ADMIN, anc, V) and not P.can_mint(admin, 4, P.ADMIN, anc, V)
    assert not P.can_mint(admin, 4, "bogus", anc, V)


def test_revoke_and_listing():
    assert P.can_revoke(planner, 6, anc, V)
    assert not P.can_revoke(planner, 11, anc, V)
    assert not P.can_revoke(worker, 6, anc, V)
    assert P.can_revoke(admin, 11, anc, V)
    assert P.can_list_tokens(admin) and P.can_list_tokens(planner) and not P.can_list_tokens(worker)
    assert P.can_manage_workorders(admin) and not P.can_manage_workorders(planner)


def test_rotate():
    # admin: any token
    assert P.can_rotate(admin, 2, P.PLANNER, 4, anc, V)
    assert P.can_rotate(admin, 3, P.WORKER, 11, anc, V)
    # planner: any token in its own workorder: a worker, itself, or another planner of the workorder
    assert P.can_rotate(planner, 3, P.WORKER, 6, anc, V)
    assert P.can_rotate(planner, 2, P.PLANNER, 4, anc, V)
    assert P.can_rotate(planner, 5, P.PLANNER, 4, anc, V)
    # planner: nothing outside its workorder
    assert not P.can_rotate(planner, 9, P.WORKER, 11, anc, V)
    assert not P.can_rotate(planner, 8, P.PLANNER, 7, anc, V)
    # node editing (rename, reparent, delete): workorder's planner or admin
    assert P.can_edit_node(planner, 6, anc, V) and P.can_edit_node(admin, 11, anc, V)
    assert not P.can_edit_node(planner, 11, anc, V) and not P.can_edit_node(worker, 6, anc, V)
    # worker: nothing, not even itself
    assert not P.can_rotate(worker, 3, P.WORKER, 6, anc, V)
