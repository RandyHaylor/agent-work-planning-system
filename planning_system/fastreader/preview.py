from typing import List

def extract_preview(lines: List[str], line_number: int, char_index: int, length: int = 30) -> str:
    """Extract a preview string from a specific line and character index.

    Args:
        lines: List of document lines
        line_number: 1-indexed line number
        char_index: Character index within the line
        length: Number of characters to extract

    Returns:
        The extracted preview string
    """
    if line_number < 1 or line_number > len(lines):
        return ""

    line = lines[line_number - 1]
    
    if char_index < 0 or char_index >= len(line):
        return ""

    preview = line[char_index:char_index + length]
    return preview
