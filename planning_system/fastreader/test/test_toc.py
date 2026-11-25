import pytest
from fastReader.toc_cli import build_toc
from fastReader.models import Manifest, Marker

def test_build_toc_basic():
    """T27, T29: build_toc(manifest, content_lines, marker_types=['sections']) returns list of dicts."""
    markers = {
        "section": [
            Marker("section", 1, 3, 0),
            Marker("section", 2, 10, 2)
        ],
        "chapter": [
            Marker("chapter", 1, 1, 0)
        ]
    }
    manifest = Manifest("test.txt", 1000, 50, markers)
    lines = ["# Chapter 1", "", "## Section 1", "Content", "", "", "", "", "", "  ## Section 2"]
    
    # Interleave line numbers correctly in our fake lines
    # Line 1: # Chapter 1
    # Line 3: ## Section 1
    # Line 10:   ## Section 2
    
    toc = build_toc(manifest, lines, marker_types=['section'])
    
    assert len(toc) == 2
    assert toc[0]["type"] == "section"
    assert toc[0]["index"] == 1
    assert toc[0]["line_number"] == 3
    assert "preview" in toc[0]
    assert toc[0]["preview"] == "## Section 1"

def test_build_toc_filter_types():
    """T28: build_toc returns only the requested marker types."""
    markers = {
        "section": [Marker("section", 1, 3, 0)],
        "chapter": [Marker("chapter", 1, 1, 0)]
    }
    manifest = Manifest("test.txt", 100, 10, markers)
    lines = ["# Chapter 1", "", "## Section 1"]
    
    toc = build_toc(manifest, lines, marker_types=['chapter'])
    assert len(toc) == 1
    assert toc[0]["type"] == "chapter"

def test_build_toc_extract_on_demand():
    """T30: build_toc preview is extracted on-demand (not from stored field)."""
    markers = {
        "section": [Marker("section", 1, 1, 3)]
    }
    manifest = Manifest("test.txt", 100, 10, markers)
    lines = ["   Actual Content starts here"]
    
    toc = build_toc(manifest, lines, marker_types=['section'], preview_length=14)
    # line[3:] is "Actual Content starts here"
    assert toc[0]["preview"] == "Actual Content"

def test_build_toc_interleave_order():
    """T31: build_toc with multiple types interleaves by line order."""
    markers = {
        "section": [Marker("section", 1, 5, 0)],
        "chapter": [Marker("chapter", 1, 1, 0)]
    }
    manifest = Manifest("test.txt", 100, 10, markers)
    lines = ["# Chapter 1", "...", "...", "...", "## Section 1"]
    
    toc = build_toc(manifest, lines, marker_types=['chapter', 'section'])
    assert len(toc) == 2
    assert toc[0]["type"] == "chapter"
    assert toc[1]["type"] == "section"

def test_build_toc_limit():
    """T32: build_toc limits to 15 entries by default."""
    markers = {"section": [Marker("section", i, i, 0) for i in range(1, 21)]}
    manifest = Manifest("test.txt", 1000, 100, markers)
    lines = ["Line" for _ in range(100)]
    
    toc = build_toc(manifest, lines, marker_types=['section'])
    assert len(toc) == 15

def test_build_toc_no_limit():
    """T33: build_toc with limit=None returns all entries."""
    markers = {"section": [Marker("section", i, i, 0) for i in range(1, 21)]}
    manifest = Manifest("test.txt", 1000, 100, markers)
    lines = ["Line" for _ in range(100)]
    
    toc = build_toc(manifest, lines, marker_types=['section'], limit=None)
    assert len(toc) == 20
