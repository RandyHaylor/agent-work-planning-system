import pytest
import os
from fastReader.models import Document, Manifest, Marker
from fastReader.scanner import scan_document


class TestMarkdownFixture:
    """Integration tests for markdown_doc.md fixture."""

    def test_document_from_file_markdown(self, markdown_fixture_path):
        """Test that Document.from_file works with markdown_doc.md."""
        doc = Document.from_file(markdown_fixture_path)
        assert doc.path == markdown_fixture_path
        assert len(doc.content) > 0
        assert len(doc.lines) > 0
        assert doc.total_chars > 0
        assert doc.total_lines > 0

    def test_scan_markdown_produces_expected_chapter_count(self, markdown_fixture_path, config):
        """Test that scanning markdown_doc.md produces 4 chapters."""
        doc = Document.from_file(markdown_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["chapter"]) == 4

    def test_scan_markdown_produces_expected_section_count(self, markdown_fixture_path, config):
        """Test that scanning markdown_doc.md produces at least 8 sections."""
        doc = Document.from_file(markdown_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["section"]) >= 8

    def test_scan_markdown_produces_subsections(self, markdown_fixture_path, config):
        """Test that scanning markdown_doc.md produces subsections."""
        doc = Document.from_file(markdown_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["subsection"]) > 0

    def test_markdown_manifest_has_valid_structure(self, markdown_fixture_path, config):
        """Test that the manifest from markdown_doc.md has valid structure."""
        doc = Document.from_file(markdown_fixture_path)
        manifest = scan_document(doc, config)

        assert isinstance(manifest, Manifest)
        assert manifest.source == markdown_fixture_path
        assert manifest.total_chars == doc.total_chars
        assert manifest.total_lines == doc.total_lines
        assert isinstance(manifest.markers, dict)
        assert all(isinstance(markers, list) for markers in manifest.markers.values())

    def test_markdown_manifest_markers_are_valid(self, markdown_fixture_path, config):
        """Test that all markers in markdown manifest are valid Marker objects."""
        doc = Document.from_file(markdown_fixture_path)
        manifest = scan_document(doc, config)

        for marker_type, markers in manifest.markers.items():
            for marker in markers:
                assert isinstance(marker, Marker)
                assert marker.marker_type == marker_type
                assert marker.index > 0
                assert marker.line > 0
                assert marker.char_index >= 0


class TestPlainTextFixture:
    """Integration tests for plain_text.txt fixture."""

    def test_document_from_file_plain_text(self, plain_text_fixture_path):
        """Test that Document.from_file works with plain_text.txt."""
        doc = Document.from_file(plain_text_fixture_path)
        assert doc.path == plain_text_fixture_path
        assert len(doc.content) > 0
        assert len(doc.lines) > 0

    def test_scan_plain_text_detects_chapters(self, plain_text_fixture_path, config):
        """Test that plain_text.txt detects 'Chapter N' patterns."""
        doc = Document.from_file(plain_text_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["chapter"]) > 0

    def test_scan_plain_text_detects_sections(self, plain_text_fixture_path, config):
        """Test that plain_text.txt detects 'Section N' patterns."""
        doc = Document.from_file(plain_text_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["section"]) > 0

    def test_scan_plain_text_detects_page_breaks(self, plain_text_fixture_path, config):
        """Test that plain_text.txt detects page break markers."""
        doc = Document.from_file(plain_text_fixture_path)
        manifest = scan_document(doc, config)
        # plain_text.txt contains --- PAGE BREAK --- markers
        assert len(manifest.markers["page_break"]) > 0

    def test_plain_text_manifest_has_valid_structure(self, plain_text_fixture_path, config):
        """Test that the manifest from plain_text.txt has valid structure."""
        doc = Document.from_file(plain_text_fixture_path)
        manifest = scan_document(doc, config)

        assert isinstance(manifest, Manifest)
        assert manifest.source == plain_text_fixture_path
        assert manifest.total_chars == doc.total_chars
        assert manifest.total_lines == doc.total_lines

    def test_plain_text_markers_have_line_numbers(self, plain_text_fixture_path, config):
        """Test that markers in plain_text.txt have valid line numbers."""
        doc = Document.from_file(plain_text_fixture_path)
        manifest = scan_document(doc, config)

        for marker_list in manifest.markers.values():
            for marker in marker_list:
                assert 1 <= marker.line <= manifest.total_lines


class TestMinimalFixture:
    """Integration tests for minimal_doc.txt fixture."""

    def test_document_from_file_minimal(self, minimal_fixture_path):
        """Test that Document.from_file works with minimal_doc.txt."""
        doc = Document.from_file(minimal_fixture_path)
        assert doc.path == minimal_fixture_path
        assert len(doc.content) > 0
        assert len(doc.lines) > 0

    def test_scan_minimal_has_few_structural_markers(self, minimal_fixture_path, config):
        """Test that minimal_doc.txt has no chapters or sections."""
        doc = Document.from_file(minimal_fixture_path)
        manifest = scan_document(doc, config)

        # Minimal doc should have no chapters, sections, or subsections
        assert len(manifest.markers["chapter"]) == 0
        assert len(manifest.markers["section"]) == 0
        assert len(manifest.markers["subsection"]) == 0

    def test_scan_minimal_creates_block_fallback(self, minimal_fixture_path, config):
        """Test that minimal_doc.txt falls back to block-based chunking."""
        doc = Document.from_file(minimal_fixture_path)
        manifest = scan_document(doc, config)

        # Should have at least one block as fallback
        assert len(manifest.markers["block"]) > 0

    def test_minimal_manifest_has_valid_structure(self, minimal_fixture_path, config):
        """Test that the manifest from minimal_doc.txt has valid structure."""
        doc = Document.from_file(minimal_fixture_path)
        manifest = scan_document(doc, config)

        assert isinstance(manifest, Manifest)
        assert manifest.source == minimal_fixture_path
        assert manifest.total_chars == doc.total_chars
        assert manifest.total_lines == doc.total_lines

    def test_minimal_blocks_cover_entire_document(self, minimal_fixture_path, config):
        """Test that blocks in minimal_doc.txt cover the entire document."""
        doc = Document.from_file(minimal_fixture_path)
        manifest = scan_document(doc, config)

        blocks = manifest.markers["block"]
        if blocks:
            # First block should have char_index 0 (or some reasonable value)
            # In our scanner, block[0] should have line=1, char_index=0
            assert blocks[0].line == 1
            assert blocks[0].char_index == 0


class TestDenseFixture:
    """Integration tests for dense_doc.md fixture."""

    def test_document_from_file_dense(self, dense_fixture_path):
        """Test that Document.from_file works with dense_doc.md."""
        doc = Document.from_file(dense_fixture_path)
        assert doc.path == dense_fixture_path
        assert len(doc.content) > 4500  # Should be ~5000 chars or more
        assert len(doc.lines) > 0

    def test_scan_dense_produces_many_chapters(self, dense_fixture_path, config):
        """Test that dense_doc.md produces multiple chapters."""
        doc = Document.from_file(dense_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["chapter"]) > 0

    def test_scan_dense_produces_many_sections(self, dense_fixture_path, config):
        """Test that dense_doc.md produces many sections."""
        doc = Document.from_file(dense_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["section"]) > 10  # Should have many sections

    def test_scan_dense_produces_many_subsections(self, dense_fixture_path, config):
        """Test that dense_doc.md produces many subsections."""
        doc = Document.from_file(dense_fixture_path)
        manifest = scan_document(doc, config)
        assert len(manifest.markers["subsection"]) > 20  # Should have many subsections

    def test_dense_manifest_has_valid_structure(self, dense_fixture_path, config):
        """Test that the manifest from dense_doc.md has valid structure."""
        doc = Document.from_file(dense_fixture_path)
        manifest = scan_document(doc, config)

        assert isinstance(manifest, Manifest)
        assert manifest.source == dense_fixture_path
        assert manifest.total_chars == doc.total_chars
        assert manifest.total_lines == doc.total_lines
        assert manifest.total_chars > 4500

    def test_dense_manifest_markers_are_valid(self, dense_fixture_path, config):
        """Test that all markers in dense manifest are valid Marker objects."""
        doc = Document.from_file(dense_fixture_path)
        manifest = scan_document(doc, config)

        marker_count = 0
        for marker_type, markers in manifest.markers.items():
            for marker in markers:
                assert isinstance(marker, Marker)
                assert marker.marker_type == marker_type
                assert marker.index > 0
                assert marker.line > 0
                assert marker.char_index >= 0
                marker_count += 1

        # Dense doc should have many markers total
        assert marker_count > 30

    def test_dense_markers_have_sequential_indices(self, dense_fixture_path, config):
        """Test that markers of each type have sequential indices."""
        doc = Document.from_file(dense_fixture_path)
        manifest = scan_document(doc, config)

        for marker_type, markers in manifest.markers.items():
            if markers:
                # Check that indices are sequential starting from 1
                for i, marker in enumerate(markers, start=1):
                    assert marker.index == i


class TestFullScanPipeline:
    """Integration tests for the full scan pipeline across all fixtures."""

    def test_all_fixtures_exist(self, markdown_fixture_path, plain_text_fixture_path,
                                 minimal_fixture_path, dense_fixture_path):
        """Test that all fixture files exist."""
        assert os.path.exists(markdown_fixture_path)
        assert os.path.exists(plain_text_fixture_path)
        assert os.path.exists(minimal_fixture_path)
        assert os.path.exists(dense_fixture_path)

    def test_scan_all_fixtures_produces_manifests(self, markdown_fixture_path, plain_text_fixture_path,
                                                   minimal_fixture_path, dense_fixture_path, config):
        """Test that scanning all fixtures produces valid Manifest objects."""
        fixtures = [
            markdown_fixture_path,
            plain_text_fixture_path,
            minimal_fixture_path,
            dense_fixture_path
        ]

        for fixture_path in fixtures:
            doc = Document.from_file(fixture_path)
            manifest = scan_document(doc, config)
            assert isinstance(manifest, Manifest)
            assert manifest.total_chars > 0
            assert manifest.total_lines > 0

    def test_all_manifests_have_required_marker_types(self, markdown_fixture_path,
                                                      plain_text_fixture_path,
                                                      minimal_fixture_path,
                                                      dense_fixture_path, config):
        """Test that all manifests contain all required marker type keys."""
        fixtures = [
            markdown_fixture_path,
            plain_text_fixture_path,
            minimal_fixture_path,
            dense_fixture_path
        ]

        required_types = ["chapter", "section", "subsection", "page_break", "page",
                         "double_line_break", "block"]

        for fixture_path in fixtures:
            doc = Document.from_file(fixture_path)
            manifest = scan_document(doc, config)

            for marker_type in required_types:
                assert marker_type in manifest.markers
                assert isinstance(manifest.markers[marker_type], list)

    def test_fixture_documents_have_consistent_properties(self, markdown_fixture_path,
                                                          plain_text_fixture_path,
                                                          minimal_fixture_path,
                                                          dense_fixture_path):
        """Test that all fixture documents have consistent size properties."""
        fixtures = [
            markdown_fixture_path,
            plain_text_fixture_path,
            minimal_fixture_path,
            dense_fixture_path
        ]

        for fixture_path in fixtures:
            doc = Document.from_file(fixture_path)

            # Document properties should be consistent
            assert doc.total_chars == len(doc.content)
            assert doc.total_lines == len(doc.lines)
            assert doc.total_chars > 0
            assert doc.total_lines > 0
