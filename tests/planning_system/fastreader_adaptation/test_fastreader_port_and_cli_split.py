"""fastReader side of the adaptation (spec integration tests 2, 3, 5, 6): commands over an
in-memory ReaderCachePort, argument_parsing and output_formatting."""
import hashlib
import os

import pytest

from planning_system.fastreader import output_formatting
from planning_system.fastreader import scanner as scanner_module
from planning_system.fastreader.argument_parsing import (intercept_help_content_flags_before_argparse,
                                                         parse_args)
from planning_system.fastreader.commands.cite import InvalidLineRange, run_cite
from planning_system.fastreader.commands.get import run_get
from planning_system.fastreader.commands.load import run_load, run_load_text
from planning_system.fastreader.commands.search import run_search
from planning_system.fastreader.commands.toc import run_toc
from planning_system.fastreader.reader_cache_port import CachedItem, ReaderCachePort, ReaderCitation
from planning_system.fastreader.scanner import load_config

FR_DIR = os.path.dirname(scanner_module.__file__)
CONFIG = load_config(os.path.join(FR_DIR, "config.json"))
FIXTURE = os.path.join(FR_DIR, "test", "fixtures", "markdown_doc.md")


class InMemoryReaderCache(ReaderCachePort):
    def __init__(self):
        self.items = {}
        self.cited = []

    def save(self, text, manifest, source_label, metadata):
        item_id = hashlib.sha256(text.encode()).hexdigest()
        self.items[item_id] = CachedItem(item_id, source_label, text, manifest, dict(metadata))
        return item_id

    def get(self, item_id):
        if item_id not in self.items:
            raise FileNotFoundError(item_id)
        return self.items[item_id]

    def cite(self, item_id, start_line, end_line):
        self.cited.append((item_id, start_line, end_line))
        return ReaderCitation(item_id, start_line, end_line)


def _text():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_load_text_id_is_full_sha256_and_stable():
    port = InMemoryReaderCache()
    first = run_load_text(_text(), "doc.md", {}, port, CONFIG)["cache_id"]
    assert len(first) == 64 and all(c in "0123456789abcdef" for c in first)
    assert run_load_text(_text(), "doc.md", {}, port, CONFIG)["cache_id"] == first


def test_line_slice_gets_a_new_id():
    port = InMemoryReaderCache()
    whole = run_load_text(_text(), "doc.md", {}, port, CONFIG)["cache_id"]
    sliced = run_load_text(_text(), "doc.md", {}, port, CONFIG, 10, 5)["cache_id"]
    assert sliced != whole and len(port.get(sliced).lines) == 5


def test_port_outputs_equal_the_file_cache_outputs(tmp_path):
    port = InMemoryReaderCache()
    mem_id = run_load_text(_text(), FIXTURE, {}, port, CONFIG)["cache_id"]
    file_id = run_load(FIXTURE, str(tmp_path), CONFIG)["manifest_id"]
    assert run_toc(mem_id, port) == run_toc(file_id, str(tmp_path))
    assert run_get(mem_id, port, section=1) == run_get(file_id, str(tmp_path), section=1)
    assert (list(run_search([mem_id], port, ["the"]).values())
            == list(run_search([file_id], str(tmp_path), ["the"]).values()))


def test_cite_checks_range_then_calls_port_with_same_id():
    port = InMemoryReaderCache()
    item_id = run_load_text("a\nb\nc", "x", {}, port, CONFIG)["cache_id"]
    with pytest.raises(InvalidLineRange):
        run_cite(port, item_id, 2, 9)
    assert port.cited == []
    assert run_cite(port, item_id, 2, 3) == ReaderCitation(item_id, 2, 3)
    assert port.cited == [(item_id, 2, 3)]


def test_argument_parsing_new_flags_and_existing_ones():
    args = parse_args(["load", "--strategy", "pypdf_text", "file.pdf"])
    assert args.strategy == "pypdf_text" and args.files == ["file.pdf"]
    assert parse_args(["load", "a.md"]).strategy is None
    cite = parse_args(["cite", "abc", "3", "9"])
    assert (cite.item_id, cite.start_line, cite.end_line) == ("abc", 3, 9)
    toc = parse_args(["toc", "--sections", "--limit", "0", "--end-sample-size", "20", "h"])
    assert toc.sections and toc.limit == 0 and toc.end_sample_size == 20
    search = parse_args(["search", "x", "y", "--manifests", "a", "b", "--all"])
    assert search.manifests == ["a", "b"] and search.match_all


def test_help_examples_without_an_id(capsys):
    assert intercept_help_content_flags_before_argparse(["toc", "--help-examples"])
    assert "toc" in capsys.readouterr().out


def test_output_formatting_load_adds_strategy_lines():
    text = output_formatting.format_load([{
        "source": "doc.pdf", "cache_id": "abc", "summary": {"sections": 2},
        "strategy_used": "pypdf_text", "available_strategies": ["pypdf_text", "ocr"]}])
    assert "  Sections: 2" in text
    assert "strategy used: pypdf_text" in text and "other strategies: ocr" in text


def test_output_formatting_load_without_strategy_is_unchanged_shape():
    text = output_formatting.format_load([{"source": "doc.md", "cache_id": "abc",
                                           "summary": {"sections": 2}}])
    assert "strategy" not in text and text.startswith("\ndoc.md")


def test_output_formatting_search():
    text = output_formatting.format_search({"abc (doc.md)": [{
        "line_number": 4, "preview": "hit", "containers": {
            "section": {"index": 1, "line_number": 3, "preview": "## S"}}}]})
    assert text == "abc (doc.md): 1 hits\n  ln 4  hit\n    section 1 ln 3  ## S"
