"""Adds " (ln S-E)" after each rendered line that carries an address; collects the ranges."""
from __future__ import annotations

from typing import Mapping, Sequence

from planning_system.quick_json_reader.json_reader_interface import JsonLineLocator
from planning_system.quick_json_reader.json_reader_types import LineRange


class AddressAnnotator:
    def annotate(self, rendered: str, locator: JsonLineLocator, node_prefix: Sequence[int] = ()
                 ) -> tuple[str, Mapping[str, LineRange]]:
        """`node_prefix` = the --show-node steps, prefixed to the relative rendered addresses. Lines that
        can't be located are returned unchanged (build log #24)."""
        raise NotImplementedError("level 7")
