"""tinycsv 2.0.0"""
__version__ = "2.0.0"


def read_rows(text, sep=",", header=True):
    """Parse CSV text into lists of strings. If header is True the first line is a header and is skipped."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if header:
        lines = lines[1:]
    return [ln.split(sep) for ln in lines]
