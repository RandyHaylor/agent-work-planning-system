"""Adds " (ln S-E)" after each rendered line that carries an address; collects the ranges."""
from __future__ import annotations

import re
from typing import Mapping, Sequence

from planning_system.quick_json_reader.json_reader_interface import JsonLineLocator
from planning_system.quick_json_reader.json_reader_types import LineRange

ADDRESS = re.compile(r"\[(\d+(?:-\d+)*)\]")  # quick-json-reader's "[1-0]" address


class AddressAnnotator:
    def annotate(self, rendered: str, locator: JsonLineLocator, node_prefix: Sequence[int] = ()
                 ) -> tuple[str, Mapping[str, LineRange]]:
        """`node_prefix` = the --show-node steps, prefixed to the relative rendered addresses. Lines that
        can't be located are returned unchanged (build log #24)."""
        lines: list[str] = []
        ranges: dict[str, LineRange] = {}
        for line in rendered.splitlines():
            match = ADDRESS.search(line)
            if match:
                steps = tuple(node_prefix) + tuple(int(step) for step in match.group(1).split("-"))
                try:
                    found = locator.locate(steps)
                except KeyError:
                    lines.append(line)
                    continue
                ranges["-".join(map(str, steps))] = found
                line = f"{line} (ln {found.start_line}-{found.end_line})"
            lines.append(line)
        return "\n".join(lines) + ("\n" if rendered.endswith("\n") else ""), ranges
