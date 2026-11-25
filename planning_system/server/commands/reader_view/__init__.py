"""reader_view: commands sharing one mechanic: an id (temp cache id or reference id) resolved to
readable text by the Reader (its ReaderCacheAdapter), then one fastReader / quick-json-reader view."""
from .reader_get import ReaderGet
from .reader_json import ReaderJson
from .reader_lines import ReaderLines
from .reader_search import ReaderSearch
from .reader_toc import ReaderToc

__all__ = ["ReaderGet", "ReaderJson", "ReaderLines", "ReaderSearch", "ReaderToc"]
