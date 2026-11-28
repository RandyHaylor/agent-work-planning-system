"""quick-json-reader integration: our copy of quick-json-reader (JavaScript, run with Node) plus the Python
side that runs it over stdin and maps its addresses to line ranges of the stored text
(spec 05-spec-quick-json-reader-integration.md). Public surface only."""
from .json_reader import JsonReader, build_json_reader
from .json_reader_interface import JsonLineLocator, JsonLineLocatorFactory, JsonReaderInterface
from .json_reader_types import (
    JsonReaderInputError, JsonReaderOutput, JsonReaderUsageError, LineRange, NodeRunResult,
)
from .node_runner import NodeRunner

__all__ = ["JsonReader", "build_json_reader", "JsonReaderInterface", "JsonLineLocator", "JsonLineLocatorFactory",
           "JsonReaderInputError", "JsonReaderOutput", "JsonReaderUsageError", "LineRange", "NodeRunResult",
           "NodeRunner"]
