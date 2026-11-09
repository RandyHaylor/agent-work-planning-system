"""Unit tests for the isolated permissions module. Pure, no IO."""
from server import permissions as P

# Tree:  1(root) -> 2(kb) -> 8(kb Product) -> 9
#                         -> 10(kb Company)
#                -> 3(plans) -> 4(project A) -> 6
#                            -> 7(project B, hidden) -> 11
#                            -> 12(project C, visible)
PARENT = {1: None, 2: 1, 3: 1, 4: 3, 6: 4, 7: 3, 8: 2, 9: 8, 10: 2, 11: 7, 12: 3}


def anc(n):
    out = []
    while n is not None:
        out.append(n)
        n = PARENT[n]
    return out


V = P.View(root=1, plans=3, kb=2, readable_projects=frozenset({4, 12}), readable_kbs=frozenset({8}))
admin = P.Principal(token_id=1, scope_node_id=1, role=P.ADMIN)
planner = P.Principal(token_id=2, scope_node_id=4, role=P.PLANNER, project_id=4)
worker = P.Principal(token_id=3, scope_node_id=6, role=P.WORKER, project_id=4)


def test_project_of_and_kb_of():
    assert P.project_of(6, anc, 3) == 4
    assert P.project_of(4, anc, 3) == 4
    assert P.project_of(3, anc, 3) is None
    assert P.project_of(9, anc, 3) is None
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


def test_planner_reads_own_visible_and_granted_projects_not_hidden():
    assert P.can_read(planner, 4, anc, V) and P.can_read(planner, 6, anc, V)
    assert P.can_read(planner, 12, anc, V)
    assert not P.can_read(planner, 7, anc, V) and not P.can_read(planner, 11, anc, V)
    assert P.can_read(planner, 1, anc, V) and P.can_read(planner, 3, anc, V) and P.can_read(planner, 2, anc, V)


def test_planner_reads_assigned_kbs_only():
    assert P.can_read(planner, 8, anc, V) and P.can_read(planner, 9, anc, V)
    assert not P.can_read(planner, 10, anc, V)
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


def test_planner_writes_only_in_own_project():
    for role in P.ALL_DOC_ROLES:
        assert P.can_write_doc(planner, 4, role, anc, V), role
        assert P.can_write_doc(planner, 6, role, anc, V), role
        assert not P.can_write_doc(planner, 12, role, anc, V), role
    assert P.can_create_child(planner, 6, anc, V)
    assert not P.can_create_child(planner, 12, anc, V)
    assert not P.can_create_child(planner, 3, anc, V)  # cannot create projects
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
    assert not P.can_mint(admin, 3, P.PLANNER, anc, V)  # a planner needs a project
    assert P.can_mint(admin, 1, P.ADMIN, anc, V) and not P.can_mint(admin, 4, P.ADMIN, anc, V)
    assert not P.can_mint(admin, 4, "bogus", anc, V)


def test_revoke_and_listing():
    assert P.can_revoke(planner, 6, anc, V)
    assert not P.can_revoke(planner, 11, anc, V)
    assert not P.can_revoke(worker, 6, anc, V)
    assert P.can_revoke(admin, 11, anc, V)
    assert P.can_list_tokens(admin) and P.can_list_tokens(planner) and not P.can_list_tokens(worker)
    assert P.can_manage_projects(admin) and not P.can_manage_projects(planner)
