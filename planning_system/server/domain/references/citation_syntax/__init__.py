"""citation_syntax: the `[ref:start-end]` citation text form and the quoted lines it points at. Pure
functions over strings; what citation_enforcement, content_review, project_tree and http_api need
without depending on the reference library."""
from .citation_format import citations_in, cites, format_citation, parse_citation
from .line_slicing import slice_lines

__all__ = ["citations_in", "cites", "format_citation", "parse_citation", "slice_lines"]
