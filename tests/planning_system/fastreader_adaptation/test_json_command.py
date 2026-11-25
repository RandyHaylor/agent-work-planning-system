"""fastReader `json` command: cached text handed to the quick-json-reader integration."""
from planning_system.fastreader.commands.json import detect_text_kind, run_json
from planning_system.fastreader.commands.load import run_load_text
from planning_system.fastreader.cli import DEFAULT_CONFIG_PATH
from planning_system.fastreader.scanner import load_config
from planning_system.quick_json_reader.fakes import FakeJsonLineLocatorFactory, FakeJsonReader, FakeNodeRunner
from planning_system.quick_json_reader.json_reader_types import NodeRunResult

CONFIG = load_config(DEFAULT_CONFIG_PATH)


def _reader(stdout="ok\n"):
    runner = FakeNodeRunner(NodeRunResult(stdout, "", 0))
    return FakeJsonReader(runner, FakeJsonLineLocatorFactory()), runner


def test_detect_text_kind():
    assert detect_text_kind('{"a": 1}') == "json"
    assert detect_text_kind('{"a": 1}\n{"a": 2}') == "jsonl"


def test_run_json_passes_the_cached_text_and_flags(tmp_path):
    port = str(tmp_path)     # the local file cache
    text = '{\n  "a": 1\n}'
    item_id = run_load_text(text, "x.json", {}, port, CONFIG)["cache_id"]
    reader, runner = _reader()
    out = run_json(port, item_id, ["--stats"], reader)
    assert runner.calls[0][0] == text and "--stats" in runner.calls[0][1]
    assert out.text == "ok\n"
