import pytest
import json
import tempfile
import os
from fastReader.scanner import load_config, scan_document
from fastReader.models import Document, Manifest, Marker


class TestLoadConfig:
    def test_load_config_returns_dict(self):
        """Test that load_config returns a dictionary."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config = {
                "chapter": {"patterns": ["Chapter \\d+", "# "]},
                "section": {"patterns": ["Section \\d+", "## "]},
            }
            json.dump(config, f)
            temp_path = f.name

        try:
            loaded = load_config(temp_path)
            assert isinstance(loaded, dict)
            assert "chapter" in loaded
            assert "section" in loaded
        finally:
            os.unlink(temp_path)

    def test_load_config_preserves_structure(self):
        """Test that load_config preserves the JSON structure."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config = {
                "chapter": {"patterns": ["Chapter \\d+"], "preview_length": 30},
                "section": {"patterns": ["Section \\d+"], "preview_length": 30},
            }
            json.dump(config, f)
            temp_path = f.name

        try:
            loaded = load_config(temp_path)
            assert loaded["chapter"]["patterns"] == ["Chapter \\d+"]
            assert loaded["chapter"]["preview_length"] == 30
        finally:
            os.unlink(temp_path)


class TestChapterDetection:
    def test_detect_chapter_with_markdown_heading(self):
        """Test that chapters are detected with '# ' markdown syntax."""
        doc = Document(
            path="test.md",
            content="# Chapter Title\nSome content",
            lines=["# Chapter Title", "Some content"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["chapter"]) > 0
        assert manifest.markers["chapter"][0].marker_type == "chapter"
        assert manifest.markers["chapter"][0].line == 1
        assert manifest.markers["chapter"][0].char_index == 0

    def test_detect_indented_chapter(self):
        """Test that indented chapters have correct char_index."""
        doc = Document(
            path="test.md",
            content="  # Indented Chapter\nSome content",
            lines=["  # Indented Chapter", "Some content"]
        )
        config = {
            "chapter": {"patterns": ["# "]},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["chapter"]) > 0
        assert manifest.markers["chapter"][0].char_index == 2

    def test_detect_multiple_chapters(self):
        """Test that multiple chapters are detected and indexed correctly."""
        doc = Document(
            path="test.md",
            content="# Chapter 1\nContent\n# Chapter 2\nMore content",
            lines=["# Chapter 1", "Content", "# Chapter 2", "More content"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["chapter"]) == 2
        assert manifest.markers["chapter"][0].index == 1
        assert manifest.markers["chapter"][1].index == 2


class TestSectionDetection:
    def test_detect_section_with_markdown_heading(self):
        """Test that sections are detected with '## ' markdown syntax."""
        doc = Document(
            path="test.md",
            content="## Section Title\nContent",
            lines=["## Section Title", "Content"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["section"]) > 0
        assert manifest.markers["section"][0].marker_type == "section"
        assert manifest.markers["section"][0].char_index == 0

    def test_detect_multiple_sections(self):
        """Test that multiple sections are detected and indexed correctly."""
        doc = Document(
            path="test.md",
            content="## Section 1\nContent\n## Section 2\nMore",
            lines=["## Section 1", "Content", "## Section 2", "More"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["section"]) == 2
        assert manifest.markers["section"][0].index == 1
        assert manifest.markers["section"][1].index == 2


class TestSubsectionDetection:
    def test_detect_subsection_with_markdown_heading(self):
        """Test that subsections are detected with '### ' markdown syntax."""
        doc = Document(
            path="test.md",
            content="### Subsection Title\nContent",
            lines=["### Subsection Title", "Content"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["subsection"]) > 0
        assert manifest.markers["subsection"][0].marker_type == "subsection"


class TestPageBreakDetection:
    def test_detect_form_feed_character(self):
        """Test that form feed characters are detected as page breaks."""
        content = "Content\f\nMore content"
        doc = Document(
            path="test.txt",
            content=content,
            lines=content.split('\n')
        )
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": ["\\f"]},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert len(manifest.markers["page_break"]) > 0
        assert manifest.markers["page_break"][0].marker_type == "page_break"


class TestDoubleLineBreakDetection:
    def test_detect_double_line_break(self):
        """Test that double line breaks are detected."""
        content = "Line 1\n\n\nLine 2"
        doc = Document(
            path="test.txt",
            content=content,
            lines=["Line 1", "", "", "Line 2"]
        )
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": ["double_break"]},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        # Double line breaks should be detected
        assert len(manifest.markers["double_line_break"]) > 0


class TestBlockFallback:
    def test_block_fallback_when_few_markers(self):
        """Test that blocks are created as fallback chunks when few structural markers exist."""
        content = "a" * 2400  # 2400 chars = 3 blocks of 800
        doc = Document(
            path="test.txt",
            content=content,
            lines=[content[i:i+80] for i in range(0, len(content), 80)]
        )
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        # Should have at least 3 blocks
        assert len(manifest.markers["block"]) >= 3

    def test_block_size_configuration(self):
        """Test that block size is configured correctly."""
        content = "a" * 1000
        doc = Document(
            path="test.txt",
            content=content,
            lines=[content[i:i+100] for i in range(0, len(content), 100)]
        )
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 500}
        }

        manifest = scan_document(doc, config)
        # With 1000 chars and 500 block size, should have 2 blocks
        assert len(manifest.markers["block"]) == 2


class TestManifestValidity:
    def test_scan_returns_manifest(self):
        """Test that scan_document returns a Manifest object."""
        doc = Document(
            path="test.md",
            content="# Chapter\nContent",
            lines=["# Chapter", "Content"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": ["^## "]},
            "subsection": {"patterns": ["^### "]},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert isinstance(manifest, Manifest)

    def test_manifest_has_correct_source(self):
        """Test that Manifest source matches the document path."""
        path = "test.md"
        doc = Document(path=path, content="Content", lines=["Content"])
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert manifest.source == path

    def test_manifest_has_correct_total_chars(self):
        """Test that Manifest total_chars is correct."""
        content = "Hello World"
        doc = Document(path="test.txt", content=content, lines=content.split())
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert manifest.total_chars == len(content)

    def test_manifest_has_correct_total_lines(self):
        """Test that Manifest total_lines is correct."""
        lines = ["Line 1", "Line 2", "Line 3"]
        content = "\n".join(lines)
        doc = Document(path="test.txt", content=content, lines=lines)
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert manifest.total_lines == len(lines)

    def test_manifest_markers_contain_all_marker_types(self):
        """Test that Manifest markers dict contains all expected marker types."""
        doc = Document(path="test.md", content="Content", lines=["Content"])
        config = {
            "chapter": {"patterns": []},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        expected_types = ["chapter", "section", "subsection", "page_break", "page", "double_line_break", "block"]
        for marker_type in expected_types:
            assert marker_type in manifest.markers
            assert isinstance(manifest.markers[marker_type], list)


class TestMarkerAttributes:
    def test_marker_has_correct_line_number(self):
        """Test that detected markers have correct line numbers."""
        doc = Document(
            path="test.md",
            content="Line 1\n# Chapter\nLine 3",
            lines=["Line 1", "# Chapter", "Line 3"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert manifest.markers["chapter"][0].line == 2

    def test_marker_has_correct_char_index(self):
        """Test that detected markers have correct character indices."""
        doc = Document(
            path="test.md",
            content="Line 1\n# Chapter\nLine 3",
            lines=["Line 1", "# Chapter", "Line 3"]
        )
        config = {
            "chapter": {"patterns": ["^# "]},
            "section": {"patterns": []},
            "subsection": {"patterns": []},
            "page_break": {"patterns": []},
            "page": {"patterns": []},
            "double_line_break": {"patterns": []},
            "block": {"size": 800}
        }

        manifest = scan_document(doc, config)
        assert manifest.markers["chapter"][0].char_index == 0
