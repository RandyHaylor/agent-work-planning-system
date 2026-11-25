"""Contract tests for the quick-json-reader integration (spec 05-spec-quick-json-reader-integration.md,
external integration tests 1-7 and 9), run against the fakes and the real classes (build log #11).
Test 8 (the JS tests) runs under `node --test` and is driven from here too."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from planning_system.quick_json_reader import (
    JsonReader, JsonReaderInputError, JsonReaderUsageError, LineRange, NodeRunResult, NodeRunner,
    build_json_reader,
)
from planning_system.quick_json_reader.fakes import (
    FakeJsonLineLocatorFactory, FakeJsonlLocator, FakeJsonReader, FakeNodeRunner, FakePrettyJsonLocator,
)
from planning_system.quick_json_reader.json_line_locator import StoredTextLocatorFactory
from planning_system.quick_json_reader.json_line_locator.jsonl_locator import JsonlLocator
from planning_system.quick_json_reader.json_line_locator.pretty_json_locator import PrettyJsonLocator
from planning_system.quick_json_reader.json_line_locator.json_source_map import JsonSourceMapLibrary
from planning_system.quick_json_reader.json_reader_types import NodeRunTimeout

FIXTURES = Path(__file__).parents[1] / "fixtures"
PACKAGE = Path(__file__).parents[3] / "planning_system" / "quick_json_reader"
STORED = (FIXTURES / "stored_pretty.json").read_text()
STORED_JSONL = (FIXTURES / "stored_records.jsonl").read_text()
# Recorded from `stdin_runner.js` on STORED with --show-full-addresses.
RENDERED = ("1 | [0] name: x\n2 | [1] items\n3 |   [1-0] 1\n4 |   [1-1]\n5 |     [1-1-0] k: true\n"
            "6 | [2] last: null\n")
RENDERED_NODE_1 = "1 | [0] 1\n2 | [1]\n3 |   [1-0] k: true\n"  # same, with --show-node 1


def make_fake_reader(runner):
    return FakeJsonReader(runner, FakeJsonLineLocatorFactory())


def make_real_reader(runner):
    return JsonReader(runner, StoredTextLocatorFactory())


READERS = [pytest.param(make_fake_reader, id="fake"), pytest.param(make_real_reader, id="real")]


# --- 1: NodeRunner with a fake subprocess function (real class only: the fake has no subprocess) ----

class FakeProcess:
    def __init__(self, timeout=False):
        self.timeout, self.kwargs, self.args = timeout, None, None

    def __call__(self, args, **kwargs):
        self.args, self.kwargs = args, kwargs
        if self.timeout:
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
        return subprocess.CompletedProcess(args, 0, stdout="out\n", stderr="")


def test_1_node_runner_sends_text_and_argv_on_stdin_without_shell():
    process = FakeProcess()
    result = NodeRunner("node", Path("stdin_runner.js"), 5.0, run_process=process).run('{"a":1}', ["--depth", "1"])
    assert result == NodeRunResult("out\n", "", 0)
    assert process.args == ["node", "stdin_runner.js"]
    assert json.loads(process.kwargs["input"]) == {"text": '{"a":1}', "argv": ["--depth", "1"]}
    assert process.kwargs.get("shell", False) is False
    assert process.kwargs["timeout"] == 5.0


def test_1_node_runner_timeout():
    with pytest.raises(NodeRunTimeout):
        NodeRunner("node", Path("x.js"), 0.1, run_process=FakeProcess(timeout=True)).run("{}", [])


# --- 2-4, 7: JsonReader ----------------------------------------------------------------------------

@pytest.mark.parametrize("make", READERS)
def test_2_addressed_lines_get_stored_text_ranges(make):
    runner = FakeNodeRunner(NodeRunResult(RENDERED, "", 0))
    output = make(runner).run(STORED, "json", ["--depth", "3"])
    assert runner.calls[0] == (STORED, ["--depth", "3", "--show-full-addresses"])
    assert output.line_ranges == {
        "0": LineRange(2, 2), "1": LineRange(3, 8), "1-0": LineRange(4, 4), "1-1": LineRange(5, 7),
        "1-1-0": LineRange(6, 6), "2": LineRange(9, 9)}
    assert "2 | [1] items (ln 3-8)" in output.text.splitlines()
    assert output.output_format == "txt"


@pytest.mark.parametrize("make", READERS)
def test_3_show_node_relative_addresses_map_to_absolute_node(make):
    runner = FakeNodeRunner(NodeRunResult(RENDERED_NODE_1, "", 0))
    output = make(runner).run(STORED, "json", ["--show-node", "1"])
    assert output.line_ranges == {"1-0": LineRange(4, 4), "1-1": LineRange(5, 7), "1-1-0": LineRange(6, 6)}
    assert output.text.splitlines()[0] == "1 | [0] 1 (ln 4-4)"


@pytest.mark.parametrize("make", READERS)
def test_4_exit_codes_map_to_errors(make):
    with pytest.raises(JsonReaderUsageError, match="unknown argument"):
        make(FakeNodeRunner(NodeRunResult("", "unknown argument: --x\n", 2))).run(STORED, "json", ["--x"])
    with pytest.raises(JsonReaderInputError, match="invalid JSON"):
        make(FakeNodeRunner(NodeRunResult("", "invalid JSON: bad\n", 1))).run("{", "json", [])


@pytest.mark.parametrize("make", READERS)
def test_7_output_json_untouched_without_ranges(make):
    runner = FakeNodeRunner(NodeRunResult('{"name": "x"}\n', "", 0))
    output = make(runner).run(STORED, "json", ["--output", "json"])
    assert runner.calls[0][1] == ["--output", "json"]
    assert (output.text, dict(output.line_ranges), output.output_format) == ('{"name": "x"}\n', {}, "json")


@pytest.mark.parametrize("make", READERS)
def test_unlocatable_lines_are_returned_without_ranges(make):
    runner = FakeNodeRunner(NodeRunResult("1 | [7] nope: 1\n", "", 0))
    output = make(runner).run(STORED, "json", [])
    assert output.text == "1 | [7] nope: 1\n"
    assert dict(output.line_ranges) == {}


# --- 5, 6: locators ---------------------------------------------------------------------------------

PRETTY = [pytest.param(FakePrettyJsonLocator, id="fake"),
          pytest.param(lambda text: PrettyJsonLocator(text, JsonSourceMapLibrary()), id="real")]
JSONL = [pytest.param(FakeJsonlLocator, id="fake"), pytest.param(JsonlLocator, id="real")]


@pytest.mark.parametrize("make", PRETTY)
def test_5_pretty_json_locator(make):
    locator = make(STORED)
    assert locator.locate([]) == LineRange(1, 10)
    assert locator.locate([1]) == LineRange(3, 8)
    assert locator.locate([1, 1]) == LineRange(5, 7)
    assert locator.locate([0]) == LineRange(2, 2)
    with pytest.raises(KeyError):
        locator.locate([9])


@pytest.mark.parametrize("make", JSONL)
def test_6_jsonl_locator(make):
    locator = make(STORED_JSONL)
    assert locator.locate([3]) == LineRange(4, 4)
    assert locator.locate([3, 2]) == LineRange(4, 4)


# --- 8: JS tests; 9: real Node end to end -------------------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_8_js_tests_pass_under_node():
    tests = sorted(str(p) for p in (PACKAGE / "tests").glob("test_*.js"))
    result = subprocess.run(["node", "--test", *tests], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_9_real_node_end_to_end_ranges_cut_back_to_values():
    output = build_json_reader({}).run(STORED, "json", [])
    lines = STORED.splitlines()
    value = json.loads(STORED)
    cut = "\n".join(lines[output.line_ranges["1"].start_line - 1:output.line_ranges["1"].end_line])
    assert json.loads("{" + cut.rstrip(",") + "}") == {"items": value["items"]}
