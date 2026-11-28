"""Reads of a superseded reference return the superseding version and a note (user 2026-11-27)."""
from __future__ import annotations

from types import SimpleNamespace

from planning_system.server import commands as C
from planning_system.server.domain.references.fakes import FakeReferenceLibrary
from planning_system.server.domain.references.line_range_mapping import MappedRange, map_line_range

OLD = "intro\nKeep two weeks.\nNightly.\nend"
NEW = "intro\nadded line\nKeep three weeks.\nNightly.\nend"


def services_with_superseded():
    library = FakeReferenceLibrary()
    old = library.store_node_text(OLD, 1)
    new = library.store_node_text(NEW, 1, replaces=old.id)
    return SimpleNamespace(references=library), old.id, new.id


def test_get_returns_newest_version_with_note():
    services, old_id, new_id = services_with_superseded()
    result = C.GetReference(old_id).run(services, None)
    assert result["id"] == new_id and result["text"] == NEW
    assert result["requested_id"] == old_id
    assert result["superseded_note"] == f"{old_id} was superseded; this is the current version {new_id}"


def test_get_of_current_reference_has_no_note():
    services, _, new_id = services_with_superseded()
    result = C.GetReference(new_id).run(services, None)
    assert result["id"] == new_id and "superseded_note" not in result


def test_lines_of_superseded_reference_carry_the_current_lines():
    services, old_id, new_id = services_with_superseded()
    result = C.ReadReferenceLines(old_id, 2, 3).run(services, None)
    assert result["text"] == "2\tKeep two weeks.\n3\tNightly."
    assert result["superseded_note"].startswith(f"{old_id} was superseded")
    # difflib sees "Keep two weeks." -> "added line / Keep three weeks." as one replaced block
    assert result["current"] == {"id": new_id, "start": 2, "end": 4,
                                 "text": "2\tadded line\n3\tKeep three weeks.\n4\tNightly.", "unchanged": False}


def test_mapping_unchanged_moved_and_deleted_ranges():
    assert map_line_range(OLD, NEW, 3, 3) == MappedRange(4, 4, True)          # moved down one line
    assert map_line_range(OLD, NEW, 2, 2) == MappedRange(2, 3, False)         # replaced (block incl. insert)
    assert map_line_range("a\nb\nc", "a\nc", 2, 2) == MappedRange(None, None, False)   # deleted
