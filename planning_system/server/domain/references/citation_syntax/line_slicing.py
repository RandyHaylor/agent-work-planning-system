"""line_slicing: the quoted text a citation points at (lines start..end of a text)."""
from planning_system.errors import Invalid


def slice_lines(text: str, start: int, end: int) -> str:
    """Lines start..end (1-based, inclusive); raises Invalid when the range is outside the text."""
    lines = text.splitlines()
    if start < 1 or end < start or end > len(lines):
        raise Invalid(f"lines {start}-{end} outside 1-{len(lines)}")
    return "\n".join(lines[start - 1:end])
