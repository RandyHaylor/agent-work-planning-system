"""In-memory fakes for the quick-json-reader integration (build log #11)."""
from __future__ import annotations

import json
import re
from typing import Mapping, Sequence

from planning_system.quick_json_reader.json_reader import carries_tree_lines, output_format, show_node_steps
from planning_system.quick_json_reader.json_reader_interface import (
    JsonLineLocator, JsonLineLocatorFactory, JsonReaderInterface, NodeRunnerInterface,
)
from planning_system.quick_json_reader.json_reader_types import (
    JsonReaderInputError, JsonReaderOutput, JsonReaderUsageError, LineRange, NodeRunResult, TextKind,
)

ADDRESS = re.compile(r"\[(\d+(?:-\d+)*)\]")


class FakeNodeRunner(NodeRunnerInterface):
    """Returns a scripted result and records every (text, argv) it was given."""

    def __init__(self, result: NodeRunResult) -> None:
        self.result = result
        self.calls: list[tuple[str, list[str]]] = []

    def run(self, text: str, argv: Sequence[str]) -> NodeRunResult:
        self.calls.append((text, list(argv)))
        return self.result


class FakePrettyJsonLocator(JsonLineLocator):
    """Assumes the stored text is json.dumps(indent=N) of its own value (json_formatter's form)."""

    def __init__(self, stored_text: str) -> None:
        self.ranges: dict[tuple[int, ...], LineRange] = {}
        self._walk(json.loads(stored_text), 1, ())

    def _walk(self, value, start: int, path: tuple[int, ...]) -> int:
        children = list(value.values()) if isinstance(value, dict) else value if isinstance(value, list) else []
        line = start
        for index, child in enumerate(children):
            line = self._walk(child, line + 1, path + (index,))
        end = line + 1 if children else start
        self.ranges[path] = LineRange(start, end)
        return end

    def locate(self, address_steps: Sequence[int]) -> LineRange:
        return self.ranges[tuple(address_steps)]


class FakeJsonlLocator(JsonLineLocator):
    def __init__(self, stored_text: str) -> None:
        self.line_count = len(stored_text.splitlines())

    def locate(self, address_steps: Sequence[int]) -> LineRange:
        if not address_steps or not 0 <= address_steps[0] < self.line_count:
            raise KeyError(tuple(address_steps))
        return LineRange(address_steps[0] + 1, address_steps[0] + 1)


class FakeJsonLineLocatorFactory(JsonLineLocatorFactory):
    def for_text(self, stored_text: str, text_kind: TextKind) -> JsonLineLocator:
        return FakeJsonlLocator(stored_text) if text_kind == "jsonl" else FakePrettyJsonLocator(stored_text)


def fake_annotate(rendered: str, locator: JsonLineLocator, prefix: Sequence[int]
                  ) -> tuple[str, Mapping[str, LineRange]]:
    lines, ranges = [], {}
    for line in rendered.splitlines():
        match = ADDRESS.search(line)
        if match:
            steps = tuple(prefix) + tuple(int(s) for s in match.group(1).split("-"))
            try:
                found = locator.locate(steps)
            except KeyError:
                lines.append(line)
                continue
            ranges["-".join(map(str, steps))] = found
            line = f"{line} (ln {found.start_line}-{found.end_line})"
        lines.append(line)
    return "\n".join(lines) + ("\n" if rendered.endswith("\n") else ""), ranges


class FakeJsonReader(JsonReaderInterface):
    """Same contract as JsonReader, annotation done in memory."""

    def __init__(self, node_runner: NodeRunnerInterface, locator_factory: JsonLineLocatorFactory) -> None:
        self.node_runner = node_runner
        self.locator_factory = locator_factory

    def run(self, stored_text: str, text_kind: TextKind, flags: Sequence[str]) -> JsonReaderOutput:
        mapped = carries_tree_lines(flags)
        argv = list(flags) + (["--show-full-addresses"] if mapped and "--show-full-addresses" not in flags else [])
        result = self.node_runner.run(stored_text, argv)
        if result.exit_code == 2:
            raise JsonReaderUsageError(result.stderr.strip())
        if result.exit_code != 0:
            raise JsonReaderInputError(result.stderr.strip())
        if not mapped:
            return JsonReaderOutput(result.stdout, {}, output_format(flags))
        text, ranges = fake_annotate(result.stdout, self.locator_factory.for_text(stored_text, text_kind),
                                     show_node_steps(flags))
        return JsonReaderOutput(text, ranges, "txt")
