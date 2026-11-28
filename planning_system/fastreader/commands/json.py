"""json command: hand a cached item's text to the quick-json-reader integration.

Results carry line ranges of the stored text, so they can be cited with `cite`.
"""
import json as _json
from typing import Any, Protocol, Sequence, Union

from ..cache import as_reader_cache
from ..reader_cache_port import ReaderCachePort


class JsonTextReader(Protocol):
    """What run_json needs from a JSON reader (e.g. quick_json_reader's JsonReaderInterface); injected
    by the caller so fastReader does not import a particular reader."""

    def run(self, text: str, kind: str, flags: list[str]) -> Any: ...


TEXT_KIND_METADATA_KEY = "text_kind"


def detect_text_kind(text: str) -> str:
    """"json" when the whole text parses as one JSON value, else "jsonl"."""
    try:
        _json.loads(text)
        return "json"
    except ValueError:
        return "jsonl"


def run_json(cache: Union[ReaderCachePort, str], item_id: str, flags: Sequence[str],
             json_reader: JsonTextReader) -> Any:
    item = as_reader_cache(cache).get(item_id)
    kind = item.metadata.get(TEXT_KIND_METADATA_KEY)
    if kind not in ("json", "jsonl"):
        kind = detect_text_kind(item.text)
    return json_reader.run(item.text, kind, list(flags))
