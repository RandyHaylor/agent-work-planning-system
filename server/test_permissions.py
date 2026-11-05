"""Unit tests for the isolated permissions module. Pure, no IO."""
from server import permissions as P

# Tree:  1(root) -> 2(kb) -> 5
#                -> 3(plans) -> 4 -> 6
PARENT = {1: None, 2: 1, 3: 1, 4: 3, 5: 2, 6: 4, 7: 1}


def anc(n):
    out = []
    while n is not None:
        out.append(n)
        n = PARENT[n]
    return out


KB = 2
root = P.Principal(token_id=1, scope_node_id=1, can_spawn=True, is_root=True)
planner = P.Principal(token_id=2, scope_node_id=3, can_spawn=True)
dev = P.Principal(token_id=3, scope_node_id=4, can_spawn=False)


def test_read_scope_and_descendants():
    assert P.can_read(dev, 4, anc, KB)
    assert P.can_read(dev, 6, anc, KB)


def test_read_ancestors():
    assert P.can_read(dev, 3, anc, KB)
    assert P.can_read(dev, 1, anc, KB)


def test_read_kb_for_everyone():
    assert P.can_read(dev, 5, anc, KB)


def test_no_read_sibling():
    assert not P.can_read(dev, 7, anc, KB)


def test_kb_write_root_only():
    assert P.can_write_doc(root, 5, 1, "summary", anc, KB)
    assert not P.can_write_doc(planner, 5, 1, "report", anc, KB)
    assert not P.can_create_child(planner, 2, anc, KB)
    assert P.can_create_child(root, 2, anc, KB)


def test_create_child_in_scope_only():
    assert P.can_create_child(dev, 4, anc, KB)
    assert P.can_create_child(dev, 6, anc, KB)
    assert not P.can_create_child(dev, 3, anc, KB)


def test_owner_only_roles():
    assert P.can_write_doc(planner, 4, planner.token_id, "instruction", anc, KB)
    assert not P.can_write_doc(dev, 4, planner.token_id, "instruction", anc, KB)
    assert not P.can_write_doc(dev, 4, planner.token_id, "summary", anc, KB)


def test_holder_roles():
    assert P.can_write_doc(dev, 4, planner.token_id, "report", anc, KB)
    assert P.can_write_doc(dev, 4, planner.token_id, "spike", anc, KB)
    assert not P.can_write_doc(dev, 3, planner.token_id, "spike", anc, KB)
    assert P.can_write_doc(dev, 6, dev.token_id, "escalation", anc, KB)
    assert not P.can_write_doc(dev, 3, planner.token_id, "report", anc, KB)


def test_edit_author_only():
    assert P.can_edit_doc(dev, 4, "report", dev.token_id, anc, KB)
    assert not P.can_edit_doc(dev, 4, "report", planner.token_id, anc, KB)


def test_never_edit_own_scope_summary_or_instruction():
    assert not P.can_edit_doc(dev, 4, "instruction", dev.token_id, anc, KB)
    assert not P.can_edit_doc(dev, 4, "summary", dev.token_id, anc, KB)
    # but on a child node it owns, yes
    assert P.can_edit_doc(dev, 6, "summary", dev.token_id, anc, KB)


def test_state_owner_or_parent_owner():
    assert P.can_set_state(planner, 4, planner.token_id, root.token_id, anc, KB)
    assert P.can_set_state(dev, 6, dev.token_id, planner.token_id, anc, KB)
    assert not P.can_set_state(dev, 4, planner.token_id, root.token_id, anc, KB)


def test_mint():
    assert P.can_mint(planner, 4, False, anc)
    assert P.can_mint(planner, 6, True, anc)
    assert not P.can_mint(dev, 6, False, anc)
    assert not P.can_mint(planner, 7, False, anc)


def test_revoke_only_minted():
    assert P.can_revoke(planner, planner.token_id)
    assert not P.can_revoke(dev, planner.token_id)
