"""reader_service: the Reader. Runs fastReader's commands (load/toc/get/search/json/cite) and the
numbered-lines view through a ReaderCacheAdapter bound to the acting principal; loads go through
Ingestion (fetch live -> document_extraction). Library errors become contract errors here."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from planning_system.contract import Invalid
from planning_system.document_extraction.extraction_types import ExtractionFailed, UnknownStrategy
from planning_system.fastreader.commands.cite import InvalidLineRange, run_cite
from planning_system.fastreader.commands.get import run_get
from planning_system.fastreader.commands.json import run_json
from planning_system.fastreader.commands.load import run_load_text
from planning_system.fastreader.commands.search import run_search
from planning_system.fastreader.commands.toc import run_toc
from planning_system.quick_json_reader import JsonReaderInputError, JsonReaderInterface, JsonReaderUsageError

from .ingestion import Ingestion
from .interface import Reader, ReferenceLibrary, TempCache
from .reader_cache_adapter import ReaderCacheAdapter
from .source_fetcher_port import FetchFailed
from .types import Citation

ADMIN = "admin"
GET_MARKERS = ("chapter", "section", "subsection", "page", "block")
SEARCH_FLAGS = {"exact": "exact", "case_sensitive": "case_sensitive", "all": "match_all",
                "match_all": "match_all"}


def reader_owner(principal) -> str:
    """Temp cache owner for a principal: its agent id; an admin session without one owns as "admin"."""
    return principal.agent_id or principal.role


def numbered(lines, start: int) -> str:
    """fastReader's read.py format: `N<tab>line`."""
    return "\n".join(f"{start + i}\t{line}" for i, line in enumerate(lines))


def _int(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Invalid(f"{name} must be a whole number") from None


def _flag(value: Any) -> bool:
    return value is True or str(value).lower() in ("1", "true", "yes")


class ReaderService(Reader):
    def __init__(self, temp_cache: TempCache, library: ReferenceLibrary, ingestion: Ingestion,
                 scanner_config: Mapping[str, Any], json_reader: Optional[JsonReaderInterface] = None):
        self._temp_cache = temp_cache
        self._library = library
        self._ingestion = ingestion
        self._config = dict(scanner_config)
        self._json_reader = json_reader

    def _port(self, principal) -> ReaderCacheAdapter:
        return ReaderCacheAdapter(self._temp_cache, self._library, reader_owner(principal),
                                  principal.role == ADMIN, self._config)

    def load(self, principal, source, strategy=None, line_start=None, line_count=None):
        try:
            loaded = self._ingestion.fetch_and_extract(source, strategy)
        except FetchFailed as error:
            raise Invalid(f"fetch failed: {error}") from error
        except ExtractionFailed as error:
            raise Invalid(f"extraction failed (attempts: {error})") from error
        except UnknownStrategy as error:
            raise Invalid(f"unknown strategy: {error}") from error
        port = self._port(principal)
        metadata = loaded.metadata()
        loaded_item = run_load_text(loaded.text, loaded.source_label, metadata, port, self._config,
                                    slice_starting_line=line_start, slice_line_count=line_count)
        cache_id = loaded_item["cache_id"]
        return [{"cache_id": cache_id, "source": loaded.source_label,
                 "toc": run_toc(cache_id, port), "summary": loaded_item["summary"],
                 "strategy_used": loaded.extraction_info.get("strategy_used"),
                 "available_strategies": list(loaded.extraction_info.get("available_strategies", ())),
                 "metadata": metadata}]

    def toc(self, principal, item_id):
        return {"id": item_id, "toc": run_toc(item_id, self._port(principal))}

    def get(self, principal, item_id, params):
        port = self._port(principal)
        markers = {name: _int(params[name], name) for name in GET_MARKERS if params.get(name) is not None}
        if markers:
            return {"id": item_id, "text": run_get(item_id, port, **markers)}
        if params.get("line_start") is not None:
            start = _int(params["line_start"], "line_start")
            count = _int(params.get("line_count", 50), "line_count")
            return self.lines(principal, item_id, start, start + count - 1)
        raise Invalid(f"get needs one of {', '.join(GET_MARKERS)} or line_start")

    def search(self, principal, terms, item_ids, options):
        keywords = [str(k) for k in options.get("keywords", ())] or terms.split()
        if not keywords:
            raise Invalid("search needs terms")
        flags = {target: _flag(options[name]) for name, target in SEARCH_FLAGS.items() if name in options}
        preview = _int(options.get("preview_length", 80), "preview_length")
        results = run_search(list(item_ids), self._port(principal), keywords, preview_length=preview, **flags)
        return {"terms": terms, "results": results}

    def json(self, principal, item_id, flags):
        if self._json_reader is None:
            raise Invalid("the json reader is not configured on this server")
        try:
            output = run_json(self._port(principal), item_id, list(flags), self._json_reader)
        except (JsonReaderUsageError, JsonReaderInputError) as error:
            raise Invalid(str(error)) from error
        ranges = {address: {"start_line": r.start_line, "end_line": r.end_line}
                  for address, r in output.line_ranges.items()}
        return {"id": item_id, "text": output.text, "line_ranges": ranges,
                "output_format": output.output_format}

    def lines(self, principal, item_id, start, end):
        lines = self._port(principal).get(item_id).lines
        start = 1 if start is None else start
        end = len(lines) if end is None else end
        if start < 1 or end < start or end > len(lines):
            raise Invalid(f"lines {start}-{end} outside 1-{len(lines)}")
        return {"id": item_id, "start": start, "end": end, "text": numbered(lines[start - 1:end], start)}

    def cite(self, principal, item_id, start_line, end_line):
        try:
            cited = run_cite(self._port(principal), item_id, start_line, end_line)
        except InvalidLineRange as error:
            raise Invalid(str(error)) from error
        return Citation(cited.item_id, cited.start_line, cited.end_line)
