from typing import Union

from planning_system.fastreader.cache import as_reader_cache
from planning_system.fastreader.reader_cache_port import ReaderCachePort, ReaderCitation


class InvalidLineRange(ValueError):
    """The requested range is outside the item's lines."""


def run_cite(cache: Union[ReaderCachePort, str], item_id: str, start_line: int, end_line: int) -> ReaderCitation:
    """Check the range against the item's line count, then cite through the port (keeps the id)."""
    port = as_reader_cache(cache)
    line_count = len(port.get(item_id).lines)
    if start_line < 1 or end_line < start_line or end_line > line_count:
        raise InvalidLineRange(f"lines {start_line}-{end_line} outside 1-{line_count}")
    return port.cite(item_id, start_line, end_line)
