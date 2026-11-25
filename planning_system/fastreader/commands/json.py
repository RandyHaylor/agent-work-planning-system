"""json command: hand a cached item's text to the quick-json-reader integration.

Results carry line ranges of the stored text, so they can be cited with `cite`.
"""
import json as _json
from typing import Sequence, Union

from planning_system.fastreader.cache import as_reader_cache
from planning_system.fastreader.reader_cache_port import ReaderCachePort
from planning_system.quick_json_reader import JsonReaderInterface, JsonReaderOutput

TEXT_KIND_METADATA_KEY = "text_kind"


def detect_text_kind(text: str) -> str:
    """"json" when the whole text parses as one JSON value, else "jsonl"."""
    try:
        _json.loads(text)
        return "json"
    except ValueError:
        return "jsonl"


def run_json(cache: Union[ReaderCachePort, str], item_id: str, flags: Sequence[str],
             json_reader: JsonReaderInterface) -> JsonReaderOutput:
    item = as_reader_cache(cache).get(item_id)
    kind = item.metadata.get(TEXT_KIND_METADATA_KEY)
    if kind not in ("json", "jsonl"):
        kind = detect_text_kind(item.text)
    return json_reader.run(item.text, kind, list(flags))
