"""Facade used by fastReader's `json` command: run quick-json-reader on stored text, annotate line ranges."""
from __future__ import annotations

from typing import Mapping, Sequence

from .address_annotator import AddressAnnotator
from .json_line_locator import StoredTextLocatorFactory
from .json_reader_interface import JsonLineLocatorFactory, JsonReaderInterface, NodeRunnerInterface
from .json_reader_types import (
    JsonReaderInputError, JsonReaderOutput, JsonReaderUsageError, OutputFormat, TextKind,
)
from .node_runner import NodeRunner

FULL_ADDRESSES_FLAG = "--show-full-addresses"
SHOW_NODE_FLAG = "--show-node"


def _flag_value(flags: Sequence[str], name: str) -> str | None:
    return flags[flags.index(name) + 1] if name in flags and flags.index(name) + 1 < len(flags) else None


def output_format(flags: Sequence[str]) -> OutputFormat:
    value = _flag_value(flags, "--output")
    return value if value in ("csv", "json") else "txt"  # type: ignore[return-value]


def carries_tree_lines(flags: Sequence[str]) -> bool:
    return output_format(flags) == "txt" and "--show-schema" not in flags


def show_node_steps(flags: Sequence[str]) -> tuple[int, ...]:
    if SHOW_NODE_FLAG not in flags:
        return ()
    start = flags.index(SHOW_NODE_FLAG) + 1
    steps: list[int] = []
    for value in flags[start:]:
        if value.startswith("--"):
            break
        steps.extend(int(part) for part in value.split("-") if part != "")
    return tuple(steps)


class JsonReader(JsonReaderInterface):
    def __init__(self, node_runner: NodeRunnerInterface, locator_factory: JsonLineLocatorFactory,
                 annotator: AddressAnnotator | None = None) -> None:
        self.node_runner = node_runner
        self.locator_factory = locator_factory
        self.annotator = annotator or AddressAnnotator()

    def run(self, stored_text: str, text_kind: TextKind, flags: Sequence[str]) -> JsonReaderOutput:
        flags = list(flags)
        mapped = carries_tree_lines(flags)
        argv = flags + [FULL_ADDRESSES_FLAG] if mapped and FULL_ADDRESSES_FLAG not in flags else flags
        result = self.node_runner.run(stored_text, argv)
        if result.exit_code == 2:
            raise JsonReaderUsageError(result.stderr.strip())
        if result.exit_code != 0:
            raise JsonReaderInputError(result.stderr.strip())
        if not mapped:
            return JsonReaderOutput(result.stdout, {}, output_format(flags))
        text, ranges = self.annotator.annotate(result.stdout, self.locator_factory.for_text(stored_text, text_kind),
                                               show_node_steps(flags))
        return JsonReaderOutput(text, ranges, "txt")


def build_json_reader(config: Mapping) -> JsonReader:
    """Factory; `config` is the "quick_json_reader" section (node_executable, timeout_seconds)."""
    return JsonReader(NodeRunner(config.get("node_executable", "node"),
                                 timeout_seconds=config.get("timeout_seconds", 30.0)),
                      StoredTextLocatorFactory())
