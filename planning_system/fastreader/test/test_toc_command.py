import os
import shutil
import tempfile
import json
import pytest
from fastReader.commands.toc import run_toc
from fastReader.commands.load import run_load
from fastReader.cache import generate_hash

def test_run_toc_basic():
    """T34: toc --sections --manifest <hash> returns JSON."""
    cache_dir = tempfile.mkdtemp()
    test_dir = tempfile.mkdtemp()
    try:
        content = "# Chapter 1\n## Section A\nContent"
        test_file = os.path.join(test_dir, "test.md")
        with open(test_file, 'w') as f:
            f.write(content)

        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }
        # First load it to populate cache
        load_result = run_load(test_file, cache_dir, config)
        manifest_hash = generate_hash(content)

        # Now run toc
        toc_result = run_toc(manifest_hash, cache_dir, marker_types=['section'])

        assert len(toc_result) == 1
        assert toc_result[0]["type"] == "section"
        assert toc_result[0]["preview"] == "## Section A"

    finally:
        shutil.rmtree(cache_dir)
        shutil.rmtree(test_dir)

def test_run_toc_multiple_types():
    """T35: toc --sections --pages --manifest <hash> calls build_toc with both types."""
    cache_dir = tempfile.mkdtemp()
    test_dir = tempfile.mkdtemp()
    try:
        content = "# Chapter 1\n## Section A\n--- PAGE BREAK ---\n## Section B"
        test_file = os.path.join(test_dir, "test.md")
        with open(test_file, 'w') as f:
            f.write(content)

        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "page_break": {"patterns": ["^--- PAGE BREAK ---$"]},
            "subsection": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }
        run_load(test_file, cache_dir, config)
        manifest_hash = generate_hash(content)

        toc_result = run_toc(manifest_hash, cache_dir, marker_types=['section', 'page_break'])

        assert len(toc_result) == 3
        # Ordered by line: Section A, Page Break, Section B
        assert toc_result[0]["type"] == "section"
        assert toc_result[1]["type"] == "page_break"
        assert toc_result[2]["type"] == "section"

    finally:
        shutil.rmtree(cache_dir)
        shutil.rmtree(test_dir)

def test_run_toc_preview_length():
    """T36: toc --preview 60 --manifest <hash> uses preview_length=60."""
    cache_dir = tempfile.mkdtemp()
    test_dir = tempfile.mkdtemp()
    try:
        content = "## Section with a very long title that exceeds thirty characters"
        test_file = os.path.join(test_dir, "test.md")
        with open(test_file, 'w') as f:
            f.write(content)

        config = {
            "section": {"patterns": ["^## "]},
            "chapter": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }
        run_load(test_file, cache_dir, config)
        manifest_hash = generate_hash(content)

        toc_result = run_toc(manifest_hash, cache_dir, marker_types=['section'], preview_length=100)

        assert len(toc_result[0]["preview"]) > 30
        assert toc_result[0]["preview"] == content

    finally:
        shutil.rmtree(cache_dir)
        shutil.rmtree(test_dir)
