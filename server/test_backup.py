"""Unit tests for the backup renderer. Pure except ``write`` into tmp_path."""
import datetime
import json

from server import backup as B

TS = datetime.datetime(2026, 11, 6, 1, 2, 3, tzinfo=datetime.timezone.utc)
NODES = [
    {"id": 5, "parent_id": 4, "title": "mod", "state": "open", "needs_review": False, "owner": 2, "created_at": TS},
    {"id": 4, "parent_id": 3, "title": "Proj A!", "state": "open", "needs_review": False, "owner": 2, "created_at": TS},
]
DOCS = [
    {"id": 9, "node_id": 5, "role": "escalation", "body": "Q?", "author": 3, "answer": "A.", "resolved": True, "created_at": TS, "updated_at": TS},
    {"id": 7, "node_id": 4, "role": "summary", "body": "line1\nline2 ", "author": 2, "answer": None, "resolved": False, "created_at": TS, "updated_at": TS},
]


def test_slug():
    assert B.slug("Proj A!") == "proj-a"
    assert B.slug("---") == "untitled"


def test_render_tree_sorted_and_iso():
    files = B.render(NODES, DOCS)
    tree = json.loads(files["tree.json"])
    assert [n["id"] for n in tree] == [4, 5]
    assert tree[0]["created_at"] == "2026-11-06T01:02:03+00:00"
    assert set(tree[0]) == set(B.NODE_FIELDS)


def test_render_doc_files():
    files = B.render(NODES, DOCS, {2: "planner", 3: "dev"})
    assert set(files) == {"tree.json", "docs/4-summary-7.md", "docs/5-escalation-9.md"}
    s = files["docs/4-summary-7.md"]
    assert s.endswith("\n\nline1\nline2 ")  # body verbatim, trailing space kept
    assert "author: planner" in s and "answer:" not in s
    e = files["docs/5-escalation-9.md"]
    assert "answer: A." in e and "resolved: true" in e and "author: dev" in e


def test_write_replaces_stale(tmp_path):
    B.write(tmp_path, B.render(NODES, DOCS))
    assert (tmp_path / "docs" / "5-escalation-9.md").exists()
    B.write(tmp_path, B.render(NODES, DOCS[1:]))
    assert not (tmp_path / "docs" / "5-escalation-9.md").exists()
    assert (tmp_path / "docs" / "4-summary-7.md").exists()


def test_backup_root_for():
    plans, kb = 3, 2
    assert B.backup_root_for([6, 5, 4, 3, 1], plans, kb) == 4
    assert B.backup_root_for([4, 3, 1], plans, kb) == 4
    assert B.backup_root_for([3, 1], plans, kb) is None
    assert B.backup_root_for([8, 2, 1], plans, kb) == kb
    assert B.backup_root_for([1], plans, kb) is None
