import os
import pytest
from fastReader.commands.search import run_search
from fastReader.commands.load import run_load
from fastReader.cache import generate_hash

CONTENT = """# Chapter One
## Section A
This line mentions async operations.
Another line here.

## Section B
### Subsection B1
This line has Async with capital A.
This line mentions both async and blocking together.
Plain line with no keywords.
"""

CONTENT2 = """# Doc Two
## Section X
This file also has async usage.
"""

CONFIG = {
    "chapter": {"patterns": ["^# "]},
    "section": {"patterns": ["^## "]},
    "subsection": {"patterns": ["^### "]},
    "page_break": {"patterns": []},
    "page": {"patterns": []},
    "double_line_break": {"patterns": []},
    "block": {"size": 800}
}


@pytest.fixture
def loaded_manifest(tmp_path):
    cache_dir = str(tmp_path / "cache")
    test_file = str(tmp_path / "doc.md")
    with open(test_file, 'w') as f:
        f.write(CONTENT)
    run_load(test_file, cache_dir, CONFIG)
    return generate_hash(CONTENT), cache_dir


@pytest.fixture
def two_manifests(tmp_path):
    cache_dir = str(tmp_path / "cache")
    file1 = str(tmp_path / "doc.md")
    file2 = str(tmp_path / "doc2.md")
    with open(file1, 'w') as f:
        f.write(CONTENT)
    with open(file2, 'w') as f:
        f.write(CONTENT2)
    run_load(file1, cache_dir, CONFIG)
    run_load(file2, cache_dir, CONFIG)
    return generate_hash(CONTENT), generate_hash(CONTENT2), cache_dir


def hits_for(results, manifest_hash):
    """Extract hits list for a given hash from grouped results."""
    key = next(k for k in results if k.startswith(manifest_hash))
    return results[key]


def test_search_basic_match(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["async"])
    hits = hits_for(results, manifest_hash)
    assert len(hits) >= 2
    for hit in hits:
        assert "async" in hit["preview"].lower()


def test_search_result_key_includes_source(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["async"])
    key = list(results.keys())[0]
    assert manifest_hash in key
    assert "doc.md" in key


def test_search_case_insensitive_by_default(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["async"])
    hits = hits_for(results, manifest_hash)
    assert len(hits) >= 2


def test_search_case_sensitive(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    hits_insensitive = hits_for(run_search([manifest_hash], cache_dir, keywords=["async"], case_sensitive=False), manifest_hash)
    hits_sensitive = hits_for(run_search([manifest_hash], cache_dir, keywords=["async"], case_sensitive=True), manifest_hash)
    assert len(hits_sensitive) < len(hits_insensitive)


def test_search_exact_match(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["async"], exact=True)
    hits = hits_for(results, manifest_hash)
    assert all("async" in h["preview"].lower() for h in hits)


def test_search_match_all(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["async", "blocking"], match_all=True)
    hits = hits_for(results, manifest_hash)
    assert len(hits) == 1
    assert "async" in hits[0]["preview"].lower()
    assert "blocking" in hits[0]["preview"].lower()


def test_search_match_any(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    hits_any = hits_for(run_search([manifest_hash], cache_dir, keywords=["async", "blocking"], match_all=False), manifest_hash)
    hits_all = hits_for(run_search([manifest_hash], cache_dir, keywords=["async", "blocking"], match_all=True), manifest_hash)
    assert len(hits_any) >= len(hits_all)


def test_search_containers_populated(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["subsection"])
    hits = hits_for(results, manifest_hash)
    assert len(hits) >= 1
    assert "containers" in hits[0]
    assert "chapter" in hits[0]["containers"]
    assert "section" in hits[0]["containers"]


def test_search_no_matches(loaded_manifest):
    manifest_hash, cache_dir = loaded_manifest
    results = run_search([manifest_hash], cache_dir, keywords=["zzznomatch"])
    hits = hits_for(results, manifest_hash)
    assert hits == []


def test_search_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_search(["badhash"], str(tmp_path), keywords=["anything"])


def test_search_multiple_manifests(two_manifests):
    hash1, hash2, cache_dir = two_manifests
    results = run_search([hash1, hash2], cache_dir, keywords=["async"])
    assert len(results) == 2
    hits1 = hits_for(results, hash1)
    hits2 = hits_for(results, hash2)
    assert len(hits1) >= 2
    assert len(hits2) >= 1


def test_search_multiple_manifests_keys(two_manifests):
    hash1, hash2, cache_dir = two_manifests
    results = run_search([hash1, hash2], cache_dir, keywords=["async"])
    keys = list(results.keys())
    assert any(hash1 in k for k in keys)
    assert any(hash2 in k for k in keys)
    assert any("doc.md" in k for k in keys)
    assert any("doc2.md" in k for k in keys)
