import pytest
import tempfile
import os
from fastReader.models import Marker, Manifest, Document


class TestMarker:
    def test_marker_creation(self):
        """Test that a Marker can be created with all required fields."""
        marker = Marker(
            marker_type="chapter",
            index=1,
            line=5,
            char_index=2
        )
        assert marker.marker_type == "chapter"
        assert marker.index == 1
        assert marker.line == 5
        assert marker.char_index == 2

    def test_marker_valid_types(self):
        """Test that Marker accepts all valid marker types."""
        valid_types = ["chapter", "section", "subsection", "page_break", "page", "double_line_break", "block"]
        for marker_type in valid_types:
            marker = Marker(
                marker_type=marker_type,
                index=1,
                line=1,
                char_index=0
            )
            assert marker.marker_type == marker_type

    def test_marker_invalid_type_raises_error(self):
        """Test that Marker raises ValueError for invalid marker types."""
        with pytest.raises(ValueError):
            Marker(
                marker_type="invalid_type",
                index=1,
                line=1,
                char_index=0
            )


class TestManifest:
    def test_manifest_creation(self):
        """Test that a Manifest can be created with all required fields."""
        markers = {
            "chapters": [
                Marker("chapter", 1, 1, 0),
                Marker("chapter", 2, 98, 0),
            ],
            "sections": [],
        }
        manifest = Manifest(
            source="spec.md",
            total_chars=24310,
            total_lines=487,
            markers=markers
        )
        assert manifest.source == "spec.md"
        assert manifest.total_chars == 24310
        assert manifest.total_lines == 487
        assert manifest.markers == markers
        assert len(manifest.markers["chapters"]) == 2


class TestDocument:
    def test_document_creation(self):
        """Test that a Document can be created with path, content, and lines."""
        content = "Line 1\nLine 2\nLine 3"
        lines = ["Line 1", "Line 2", "Line 3"]
        doc = Document(path="/path/to/file.txt", content=content, lines=lines)
        assert doc.path == "/path/to/file.txt"
        assert doc.content == content
        assert doc.lines == lines

    def test_document_total_chars_property(self):
        """Test that total_chars property returns the length of content."""
        content = "Hello World"
        doc = Document(path="/path/to/file.txt", content=content, lines=content.split())
        assert doc.total_chars == len(content)

    def test_document_total_lines_property(self):
        """Test that total_lines property returns the number of lines."""
        lines = ["Line 1", "Line 2", "Line 3"]
        content = "\n".join(lines)
        doc = Document(path="/path/to/file.txt", content=content, lines=lines)
        assert doc.total_lines == len(lines)

    def test_document_from_file(self):
        """Test that Document.from_file() reads a file correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            content = "First line\nSecond line\nThird line"
            f.write(content)
            temp_path = f.name

        try:
            doc = Document.from_file(temp_path)
            assert doc.path == temp_path
            assert doc.content == content
            assert doc.lines == ["First line", "Second line", "Third line"]
            assert doc.total_chars == len(content)
            assert doc.total_lines == 3
        finally:
            os.unlink(temp_path)
