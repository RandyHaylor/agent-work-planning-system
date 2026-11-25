import os
import shutil
import tempfile
import pytest
from fastReader.commands.get import run_get
from fastReader.commands.load import run_load
from fastReader.cache import generate_hash

def test_run_get_section():
    """Test retrieving a specific section's content."""
    cache_dir = tempfile.mkdtemp()
    test_dir = tempfile.mkdtemp()
    try:
        content = "# Chapter 1\n## Section A\nContent inside A\n## Section B\nContent inside B"
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
        run_load(test_file, cache_dir, config)
        h = generate_hash(content)

        # Get Section 1 (Section A)
        result = run_get(h, cache_dir, section=1)
        assert "Section A" in result
        assert "Content inside A" in result
        assert "Section B" not in result

    finally:
        shutil.rmtree(cache_dir)
        shutil.rmtree(test_dir)

def test_run_get_chapter():
    """Test retrieving an entire chapter."""
    cache_dir = tempfile.mkdtemp()
    test_dir = tempfile.mkdtemp()
    try:
        content = "# Chapter 1\nSection A\n# Chapter 2\nSection B"
        test_file = os.path.join(test_dir, "test.md")
        with open(test_file, 'w') as f:
            f.write(content)

        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }
        run_load(test_file, cache_dir, config)
        h = generate_hash(content)

        result = run_get(h, cache_dir, chapter=1)
        assert "# Chapter 1" in result
        assert "Section A" in result
        assert "# Chapter 2" not in result
    finally:
        shutil.rmtree(cache_dir)
        shutil.rmtree(test_dir)

def test_run_get_subsection():
    """Test retrieving a specific subsection's content."""
    cache_dir = tempfile.mkdtemp()
    test_dir = tempfile.mkdtemp()
    try:
        content = "# Chapter 1\n## Section A\n### Subsection A1\nContent in A1\n### Subsection A2\nContent in A2"
        test_file = os.path.join(test_dir, "test.md")
        with open(test_file, 'w') as f:
            f.write(content)

        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }
        run_load(test_file, cache_dir, config)
        h = generate_hash(content)

        # Get Subsection 1 (Subsection A1)
        result = run_get(h, cache_dir, subsection=1)
        assert "Subsection A1" in result
        assert "Content in A1" in result
        assert "Subsection A2" not in result

    finally:
        shutil.rmtree(cache_dir)
        shutil.rmtree(test_dir)
