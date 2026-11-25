"""reader_view: commands sharing one mechanic: resolve an id (temp cache id or reference id) to readable
text, then run one fastReader / quick-json-reader view."""
from .reader_get import ReaderGet
from .reader_json import ReaderJson
from .reader_lines import ReaderLines
from .reader_search import ReaderSearch
from .reader_toc import ReaderToc
from .readable_text_resolver import ReadableText, ReadableTextResolver

__all__ = ["ReadableText", "ReadableTextResolver", "ReaderGet", "ReaderJson", "ReaderLines",
           "ReaderSearch", "ReaderToc"]
