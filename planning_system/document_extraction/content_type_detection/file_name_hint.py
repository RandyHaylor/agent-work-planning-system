from __future__ import annotations

from pathlib import PurePosixPath

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_EXTENSIONS = {
    ".pdf": "application/pdf", ".docx": DOCX, ".json": "application/json", ".jsonl": "application/jsonl",
    ".ndjson": "application/jsonl", ".md": "text/markdown", ".markdown": "text/markdown",
    ".txt": "text/plain", ".html": "text/html", ".htm": "text/html",
}


def media_type_from_file_name(file_name: str | None) -> str | None:
    """Extension of an uploaded file name: .pdf, .docx, .json, .jsonl, .md, .txt, .html."""
    if not file_name:
        return None
    return _EXTENSIONS.get(PurePosixPath(file_name.replace("\\", "/")).suffix.lower())
