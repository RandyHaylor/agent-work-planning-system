"""reader: the agent-facing reader over fastReader and quick-json-reader (load, toc, get, search, json,
cite). Owns all fastReader / quick-json-reader coupling of references. `reader_cache_adapter_fakes` is
its test-support submodule."""
from .reader_cache_adapter import ReaderCacheAdapter
from .reader_service import ReaderService, numbered, reader_owner

__all__ = ["ReaderCacheAdapter", "ReaderService", "numbered", "reader_owner"]
