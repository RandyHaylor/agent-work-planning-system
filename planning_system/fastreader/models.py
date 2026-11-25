import re
from dataclasses import dataclass
from typing import Dict, List

VALID_MARKER_TYPES = {"chapter", "section", "subsection", "page_break", "page", "double_line_break", "block"}

# Depth-suffixed marker kinds: indent_depth_0, indent_depth_1, ...; bracket_depth_0, bracket_depth_1, ...
# These are produced by the two new structural scanners (indent-level transitions and
# bracket-nesting transitions) and may appear at any non-negative integer depth.
_VALID_DEPTH_MARKER_PATTERN = re.compile(r'^(indent_depth|bracket_depth|tag_depth)_\d+$')


@dataclass
class Marker:
    """Represents a structural marker in a document."""
    marker_type: str
    index: int
    line: int
    char_index: int  # Within-line position where content starts (after whitespace)
    children_count: int = 0  # Number of immediate child markers beneath this one
    line_span: int = 0  # Distance (in lines) to the next same-kind marker or end-of-file

    def __post_init__(self):
        if self.marker_type in VALID_MARKER_TYPES:
            return
        if _VALID_DEPTH_MARKER_PATTERN.match(self.marker_type):
            return
        raise ValueError(f"marker_type not recognized: {self.marker_type}")


@dataclass
class Manifest:
    """Represents a document manifest with structural markers."""
    source: str
    total_chars: int
    total_lines: int
    markers: Dict[str, List[Marker]]


@dataclass
class Document:
    """Represents a document with its path, content, and lines."""
    path: str
    content: str
    lines: List[str]

    @classmethod
    def from_file(cls, path: str) -> "Document":
        """Load a document from a file."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.split('\n')
        return cls(path=path, content=content, lines=lines)

    @property
    def total_chars(self) -> int:
        """Return the total number of characters in the document."""
        return len(self.content)

    @property
    def total_lines(self) -> int:
        """Return the total number of lines in the document."""
        return len(self.lines)
